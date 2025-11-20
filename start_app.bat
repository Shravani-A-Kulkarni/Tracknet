@echo off
echo Starting TrackNet Application...

echo Starting Flask Backend...
cd backend
start cmd /k "python app.py"

echo Waiting 15 seconds for Flask backend to load all models...
timeout /t 15

echo Starting Frontend Server...
cd ..\frontend
start cmd /k "python -m http.server 8000"

echo Waiting for frontend server to start...
timeout /t 3

echo Opening Application in Chrome...
start chrome http://localhost:8000/index.html

echo Both servers started! 
echo Backend: localhost:5000 
echo Frontend: localhost:8000
echo.
echo IMPORTANT: Wait until you see Flask output showing models are loaded!
echo Then refresh the browser page if you see errors.
pause