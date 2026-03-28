@echo off
chcp 65001 > nul
echo ========================================
echo  Tube Research 필수 모듈 설치
echo ========================================
echo.
echo 필요한 Python 모듈을 설치합니다...
echo.

pip install -r requirements.txt

echo.
echo ========================================
echo  설치 완료!
echo ========================================
echo.
echo 이제 start.bat을 실행하여 프로그램을 시작할 수 있습니다.
echo.
pause
