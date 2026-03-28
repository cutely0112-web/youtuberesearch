@echo off
chcp 65001 > nul
REM --- Tube Research 실행 스크립트 (포트 8000) ---

echo 백엔드 서버를 시작합니다...
echo 서버 로그를 보려면 새로 열린 창을 확인하세요.
echo.
REM Python 스크립트를 직접 실행 (포트 8000)
start "Tube Research Backend" cmd /k python youtubereserch.py


echo 브라우저 시작까지 3초간 기다립니다...
timeout /t 3 /nobreak > nul

echo 웹 브라우저를 시작합니다...
start http://127.0.0.1:8000/

echo.
echo 완료! 서버가 http://127.0.0.1:8000 에서 실행 중입니다.
echo 서버를 종료하려면 백엔드 창에서 Ctrl+C를 누르세요.
echo.
echo 이 창은 3초 후 자동으로 닫힙니다...
timeout /t 3 /nobreak > nul
exit