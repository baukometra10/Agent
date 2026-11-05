from app.agents.hierarchy import classify_intent, looks_like_product_build


def test_arabic_website_brief_routes_to_design():
    route = classify_intent("ابني موقع حجوزات بسيط بواجهة عربية")
    assert looks_like_product_build("ابني موقع حجوزات بسيط بواجهة عربية")
    assert route.intent == "design"
    assert classify_intent("ابني موقع").intent == "design"


def test_build_app_routes_to_implement_or_design():
    route = classify_intent("build a small FastAPI health service with README")
    assert looks_like_product_build("build a small FastAPI health service with README")
    assert route.intent in {"implement", "design"}


def test_analyze_question_stays_analyze():
    route = classify_intent("اشرح كيف يعمل نظام المصادقة هنا")
    assert route.intent == "analyze"
