"""Server-rendered dashboard views for the FMU Gateway."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import FMUPackage, License, Listing, Purchase, SKUType, UsageLog, User, ValidationJob
from ..models.user import LoginRequest, UserCreate
from ..services.auth_service import AuthService
from ..services.billing_service import BillingService
from ..services.frontend_service import frontend_service, get_current_user
from ..services.marketplace_service import marketplace_service
from ..services.object_storage import generate_signed_url
from ..services.stripe_service import StripeService
from . import auth as auth_routes

router = APIRouter(include_in_schema=False)

settings = get_settings()
stripe_service = StripeService()
auth_service = AuthService()
billing_service = BillingService()


def _determine_plan(user: User) -> str:
    if user.credits >= settings.pricing["enterprise"]["credits"]:
        return "Enterprise"
    if user.credits >= settings.pricing["pro"]["credits"]:
        return "Pro"
    return "Free"


def _chart_data(logs: list[UsageLog]) -> dict[str, list[Any]]:
    labels = []
    usage_values = []
    credits = []
    for log in reversed(logs):
        labels.append(log.timestamp.strftime("%b %d"))
        usage_values.append(log.credits_used)
        credits.append(max(log.credits_used, 1))
    return {"labels": labels, "usage": usage_values, "credits": credits}


@router.get("/")
def root_redirect(request: Request) -> Any:
    token = request.cookies.get(auth_service.jwt_cookie_name)
    target = "/dashboard" if token else "/login"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login")
async def login_page(request: Request) -> Any:
    frontend_service.rate_limit(request)
    return frontend_service.render(request, "login.html", {"title": "Sign In"})


@router.post("/login")
async def login_submit(request: Request, session: Session = Depends(get_session)) -> Any:
    frontend_service.rate_limit(request)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = LoginRequest(**(await request.json()))
        return auth_routes.login(payload, session)

    form = await request.form()
    frontend_service.assert_csrf(request, form.get("csrf_token"))

    email = form.get("email", "").strip()
    password = form.get("password", "").strip()
    api_key = form.get("api_key", "").strip()

    login_payload = LoginRequest(
        email=email or None,
        password=password or None,
        api_key=api_key or None,
    )
    try:
        api_response = auth_routes.login(login_payload, session)
    except HTTPException as exc:
        response = frontend_service.render(
            request,
            "login.html",
            {
                "title": "Sign In",
                "error": "Invalid credentials. Use your registered email/password or API key.",
                "email": email,
            },
        )
        response.status_code = exc.status_code
        return response

    token = api_response["token"]
    return frontend_service.create_session_response(token)


@router.get("/register")
async def register_page(request: Request) -> Any:
    frontend_service.rate_limit(request)
    return frontend_service.render(request, "register.html", {"title": "Create Account"})


@router.post("/register")
async def register_submit(request: Request, session: Session = Depends(get_session)) -> Any:
    frontend_service.rate_limit(request)
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = UserCreate(**(await request.json()))
        result = auth_routes.register(payload, session)
        return JSONResponse(
            content=result.model_dump(by_alias=True),
            status_code=status.HTTP_201_CREATED,
        )

    form = await request.form()
    frontend_service.assert_csrf(request, form.get("csrf_token"))

    email = form.get("email", "").strip()
    name = form.get("name", "").strip() or None
    password = form.get("password", "").strip()

    if not email or not password:
        response = frontend_service.render(
            request,
            "register.html",
            {
                "title": "Create Account",
                "error": "Email and password are required.",
                "email": email,
                "name": name or "",
            },
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response

    try:
        payload = UserCreate(email=email, name=name, password=password)
        registration = auth_routes.register(payload, session)
    except HTTPException as exc:
        response = frontend_service.render(
            request,
            "register.html",
            {
                "title": "Create Account",
                "error": "User already exists. Please log in instead.",
                "email": email,
                "name": name or "",
            },
        )
        response.status_code = exc.status_code
        return response

    user = auth_service.get_user(session, registration.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User creation failed")

    token = auth_service.issue_token(user.id)
    return frontend_service.create_session_response(token)


@router.get("/logout")
async def logout() -> Any:
    return frontend_service.clear_session()


@router.get("/dashboard")
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    usage_logs = (
        session.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.timestamp.desc())
        .limit(7)
        .all()
    )
    chart = _chart_data(usage_logs)

    context = {
        "title": "Dashboard",
        "user": user,
        "plan": _determine_plan(user),
        "chart": chart,
        "docs_url": "/docs/sdk_usage.md",
    }
    return frontend_service.render(request, "dashboard.html", context)


@router.get("/billing")
async def billing(
    request: Request,
    user: User = Depends(get_current_user),
) -> Any:
    context = {
        "title": "Billing",
        "user": user,
        "plan": _determine_plan(user),
        "pricing": settings.pricing,
        "public_portal": settings.public_billing_portal,
    }
    return frontend_service.render(request, "billing.html", context)


@router.post("/billing/checkout")
async def create_checkout(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    form = await request.form()
    frontend_service.assert_csrf(request, form.get("csrf_token"))

    plan = form.get("plan")
    plan_details = settings.pricing.get(plan or "")
    if not plan_details:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    # Stripe checkout session creation hooks into the existing billing service.
    checkout = stripe_service.create_checkout_session(
        customer_id=user.stripe_customer_id,
        plan=plan,
        amount_cents=int(plan_details["amount_cents"]),
        description=str(plan_details["description"]),
        metadata={"user_id": user.id, "plan": plan},
    )

    billing_service.log_usage(session, user, f"checkout_{plan}", 0)

    return RedirectResponse(url=checkout["url"], status_code=status.HTTP_303_SEE_OTHER)


@router.get("/creator/console")
async def creator_console(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    creator = user.creator_profile
    if not creator:
        context = {"title": "Creator Console", "user": user, "error": "Apply as a creator to unlock publishing tools."}
        return frontend_service.render(request, "creator_console.html", context)

    packages = (
        session.query(FMUPackage)
        .filter(FMUPackage.creator_id == creator.id)
        .order_by(FMUPackage.created_at.desc())
        .limit(10)
        .all()
    )
    jobs = (
        session.query(ValidationJob)
        .join(FMUPackage)
        .filter(FMUPackage.creator_id == creator.id)
        .order_by(ValidationJob.started_at.desc())
        .limit(10)
        .all()
    )
    job_payload = [
        {
            "version": job.version,
            "status": job.status,
            "report_key": job.report_key,
            "report_url": generate_signed_url(job.report_key) if job.report_key else None,
        }
        for job in jobs
    ]
    context = {
        "title": "Creator Console",
        "user": user,
        "packages": packages,
        "validation_jobs": job_payload,
    }
    return frontend_service.render(request, "creator_console.html", context)


@router.get("/marketplace")
async def marketplace_page(request: Request, session: Session = Depends(get_session)) -> Any:
    query = request.query_params.get("q")
    certified_only = request.query_params.get("certified_only") == "1"
    packages = marketplace_service.search_packages(
        session,
        query=query,
        tags=None,
        certified_only=certified_only,
        sort=request.query_params.get("sort"),
    )
    context = {
        "title": "Marketplace",
        "query": query or "",
        "certified_only": certified_only,
        "packages": packages,
    }
    return frontend_service.render(request, "marketplace.html", context)


@router.get("/account/licenses")
async def buyer_account(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    licenses = (
        session.query(License)
        .filter(License.buyer_user_id == user.id)
        .join(Purchase)
        .join(Listing)
        .all()
    )
    data = []
    for license_obj in licenses:
        entitlement = license_obj.entitlements
        download_url = None
        if license_obj.purchase.listing.sku_type == SKUType.DOWNLOAD and not license_obj.is_revoked:
            download_url = generate_signed_url(license_obj.version.file_key)
        data.append(
            {
                "id": license_obj.id,
                "package_id": license_obj.package_id,
                "version_id": license_obj.version_id,
                "scope": license_obj.scope.value,
                "seats": license_obj.seats,
                "is_revoked": license_obj.is_revoked,
                "runs_remaining": entitlement.runs_remaining if entitlement else None,
                "download_url": download_url,
            }
        )

    context = {
        "title": "Buyer Account",
        "user": user,
        "licenses": data,
    }
    return frontend_service.render(request, "buyer_account.html", context)


@router.get("/usage")
async def usage_page(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    logs = (
        session.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.timestamp.desc())
        .limit(100)
        .all()
    )
    context = {
        "title": "Usage",
        "user": user,
        "logs": logs,
    }
    return frontend_service.render(request, "usage.html", context)


@router.get("/api-keys")
async def api_keys_page(
    request: Request,
    user: User = Depends(get_current_user),
) -> Any:
    context = {
        "title": "API Keys",
        "user": user,
        "keys": user.api_keys,
    }
    return frontend_service.render(request, "api_keys.html", context)
