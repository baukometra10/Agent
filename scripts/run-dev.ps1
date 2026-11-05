# Evolve launcher — يوجّه إلى ملف التشغيل الرئيسي في جذر المشروع
# الاستخدام المفضّل:
#   cd c:\Users\u4363\Desktop\Agent
#   .\start.ps1

$Root = Split-Path -Parent $PSScriptRoot
& (Join-Path $Root "start.ps1")
