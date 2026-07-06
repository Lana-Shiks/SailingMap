# launch.ps1
Write-Host "Starting Backend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\Lana\Desktop\Projects\SailingMapV2; uvicorn services.router.main:app --reload --port 8000"

Write-Host "Starting Agent..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\Lana\Desktop\Projects\SailingMapV2; uvicorn agents.concierge_agent:app --reload --port 8001"

Write-Host "Starting Frontend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd c:\Users\Lana\Desktop\Projects\SailingMapV2\frontend; npm run dev"

Write-Host "Services launched in separate windows."
