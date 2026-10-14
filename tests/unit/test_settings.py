from deribit_tracker.config import Settings


def test_database_url_escapes_special_characters_in_password() -> None:
    settings = Settings(
        postgres_user="tracker",
        postgres_password="p@ss/w:rd",
        postgres_host="postgres",
        postgres_port=5432,
        postgres_db="prices",
    )

    url = settings.database_url

    assert url.password == "p@ss/w:rd"
    assert url.host == "postgres"
    assert url.database == "prices"
    assert "p%40ss%2Fw%3Ard" in url.render_as_string(hide_password=False)
