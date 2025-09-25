Write-Output "FMU Gateway Fly.io Setup Script - Run this to fix deployment and test transaction"

# Step 1: Install Fly CLI if not installed
if (-not (Get-Command fly -ErrorAction SilentlyContinue)) {
    Write-Output "Installing Fly CLI..."
    iwr https://fly.io/install.ps1 -useb | iex
    $env:PATH += ";$env:USERPROFILE\.fly\bin"
    [Environment]::SetEnvironmentVariable("Path", $env:PATH, "User")
    Write-Output "Fly CLI installed. Restart PowerShell if needed."
}

# Step 2: Login to Fly (opens browser)
Write-Output "Logging in to Fly.io (open browser and complete)..."
fly auth login

# Step 3: Check/Create App
Write-Output "Checking/creating app 'fmu-gateway'..."
fly launch --name fmu-gateway --no-deploy  # No deploy, just config if missing

# Step 4: Create Postgres DB
Write-Output "Creating Postgres DB 'fmu-gateway-db'..."
fly postgres create --name fmu-gateway-db

# Step 5: Attach DB to App
Write-Output "Attaching DB to app..."
fly postgres attach fmu-gateway-db --app fmu-gateway

# Step 6: Set Secrets (replace with your values)
# TODO: Replace these with your actual Stripe test key
$stripe_key = Read-Host "Enter your Stripe test secret key (sk_test_...)"
fly secrets set STRIPE_SECRET_KEY=$stripe_key --app fmu-gateway
fly secrets set STRIPE_ENABLED=true --app fmu-gateway

# Optional Redis (skip or set Upstash URL)
# $redis_url = Read-Host "Enter Redis URL (or skip)"
# fly secrets set REDIS_URL=$redis_url --app fmu-gateway

# Step 7: Deploy/ Restart App
Write-Output "Deploying and restarting app..."
fly deploy --app fmu-gateway
fly machines restart --app fmu-gateway

# Step 8: Wait and Test
Write-Output "Waiting 60s for deployment..."
Start-Sleep -Seconds 60

Write-Output "Testing root endpoint..."
$response = Invoke-WebRequest -Uri https://fmu-gateway.fly.dev
Write-Output "Root Status: $($response.StatusCode)"
if ($response.StatusCode -eq 200) {
    Write-Output "Success! App is live."
    
    # Generate key
    $keyResp = Invoke-WebRequest -Uri https://fmu-gateway.fly.dev/keys -Method Post
    $api_key = ($keyResp.Content | ConvertFrom-Json).key
    Write-Output "Generated API Key: $api_key"
    
    # Test unpaid sim (402)
    $body = @{fmu_id="msl:BouncingBall"; stop_time=1.0; step=0.01; kpis=@("y_rms")} | ConvertTo-Json
    $unpaid = Invoke-WebRequest -Uri https://fmu-gateway.fly.dev/simulate -Method Post -Headers @{
        "Authorization" = "Bearer $api_key"
        "Content-Type" = "application/json"
    } -Body $body
    Write-Output "Unpaid Sim Status: $($unpaid.StatusCode)"
    Write-Output "Unpaid Response: $($unpaid.Content)"
    
    # Test paid sim
    $paidBody = @{fmu_id="msl:BouncingBall"; stop_time=1.0; step=0.01; kpis=@("y_rms"); payment_token="tok_visa"; payment_method="stripe_card"} | ConvertTo-Json
    $paid = Invoke-WebRequest -Uri https://fmu-gateway.fly.dev/simulate -Method Post -Headers @{
        "Authorization" = "Bearer $api_key"
        "Content-Type" = "application/json"
    } -Body $paidBody
    Write-Output "Paid Sim Status: $($paid.StatusCode)"
    Write-Output "Paid Response (truncated): $($paid.Content.Substring(0, 200))"
    Write-Output "Check Stripe dashboard for test charge!"
} else {
    Write-Output "App not ready yet. Run 'fly logs --app fmu-gateway' for errors."
}
