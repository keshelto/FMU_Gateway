# FMU Gateway Payments and Access Pipeline

## Authentication (`private-api/app/routes/auth.py`)
```python
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: Session = Depends(get_session)) -> UserResponse:
    existing = session.query(User).filter(User.email == payload.email).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    customer_id = stripe_service.create_customer(payload.email, payload.name)

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        name=payload.name,
        api_key=str(uuid.uuid4()),
        stripe_customer_id=customer_id,
        credits=settings.free_tier_credits,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    billing_service.log_usage(session, user, "registration_bonus", 0)

    return UserResponse.from_orm(user)
```

## Billing (`private-api/app/routes/billing.py`)
```python
@router.post("/purchase")
def purchase(payload: PurchaseRequest, session: Session = Depends(get_session)) -> dict:
    user = auth_service.authenticate_api_key(session, payload.api_key)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    plan_name = payload.plan
    plan_details = settings.pricing.get(plan_name)
    if not plan_details:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    metadata = {
        "user_id": user.id,
        "plan": plan_name,
        "success_url": f"{settings.public_billing_portal}/success",
        "cancel_url": f"{settings.public_billing_portal}/cancel",
    }

    checkout = stripe_service.create_checkout_session(
        customer_id=user.stripe_customer_id,
        plan=plan_name,
        amount_cents=int(plan_details["amount_cents"]),
        description=str(plan_details["description"]),
        metadata=metadata,
    )

    return {"checkout_url": checkout["url"], "session_id": checkout["id"]}
```

## FMU Execution (`private-api/app/routes/execute_fmu.py`)
```python
@router.post("/execute_fmu", response_model=FMUExecutionResult)
async def execute_fmu(
    fmu: UploadFile = File(...),
    payload: str = Form("{}"),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> FMUExecutionResult:
    user = _resolve_user(session, authorization, x_api_key)
    _enforce_rate_limit(user.id)

    try:
        payload_dict = json.loads(payload or "{}")
        request_model = FMUExecutionRequest(**payload_dict)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload JSON") from exc

    if user.credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Your credits are low. Visit billing portal at {settings.public_billing_portal}",
        )

    fmu_bytes = await fmu.read()
    start_time = time.monotonic()
    runner_result = runner.run(fmu_bytes, request_model.parameters)
    elapsed = time.monotonic() - start_time

    credits_consumed = max(1, int(request_model.metadata.get("credit_cost", 1)))
    try:
        billing_service.deduct_credits(session, user, credits_consumed)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Your credits are low. Visit billing portal at {settings.public_billing_portal}",
        ) from None

    billing_service.log_usage(session, user, request_model.metadata.get("fmu_name", fmu.filename or "unknown"), credits_consumed)

    return FMUExecutionResult(
        status=runner_result["status"],
        output_url=f"{settings.public_billing_portal}/results/{user.id}/{int(time.time())}.zip",
        execution_time=elapsed,
        credits_consumed=credits_consumed,
    )
```

## SDK (`open-sdk/fmu_gateway_sdk/client.py`)
```python
def execute(
    self,
    fmu_path: str | Path,
    parameters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        return self._execute(fmu_path, parameters, metadata)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 402:
            raise RuntimeError(
                "Your credits are low. Visit billing portal at https://fmu-gateway.ai/billing"
            ) from exc
        raise
```

## Testing (`tests/test_payments.py`)
```python
def test_credit_purchase_and_execution(monkeypatch: pytest.MonkeyPatch, private_api):
    client, module = private_api

    auth_module = sys.modules["private_api_app.routes.auth"]
    billing_module = sys.modules["private_api_app.routes.billing"]

    monkeypatch.setattr(auth_module.stripe_service, "create_customer", lambda email, name: "cus_123")
    monkeypatch.setattr(billing_module.stripe_service, "create_checkout_session", fake_checkout)
    monkeypatch.setattr(billing_module.stripe_service, "parse_event", fake_event)

    register_resp = client.post("/register", json={"email": "tester@example.com", "name": "Tester"})
    login_resp = client.post("/login", json={"api_key": api_key})
    purchase_resp = client.post("/purchase", json={"api_key": api_key, "plan": "pro"})
    webhook_resp = client.post("/stripe/webhook", json=webhook_payload)
    execute_resp = client.post(
        "/execute_fmu",
        files={**files, **payload},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert execute_resp.status_code == 200
```
