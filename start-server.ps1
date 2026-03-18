$python = "C:\Users\adars\AppData\Local\Programs\Python\Python314\python.exe"

if (-not (Test-Path $python)) {
  throw "Python not found at $python"
}

& $python "$PSScriptRoot\server.py"
