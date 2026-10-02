from newsx.web import NewsxApplication, model_json


def test_model_json_serializes_pydantic_models():
    from newsx.schemas import Source, SourceTier

    source = Source(
        id="test-source",
        name="Test Source",
        tier=SourceTier.PRIMARY,
        ownership="Public",
        funding="Public",
        region="Test",
        language="en",
        medium="official",
    )
    assert model_json(source)["tier"] == "primary"


def test_web_application_reports_existing_pipeline_state():
    application = NewsxApplication()
    health = application.health()

    assert health["service"] == "TrueNews local editorial engine"
    assert health["status"] == "ok"
    assert isinstance(application.events(), list)
