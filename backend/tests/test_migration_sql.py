import re
from pathlib import Path


def test_supabase_migration_exists_and_is_timestamped():
    migrations_dir = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
    assert migrations_dir.is_dir(), "supabase/migrations directory must exist"

    sql_files = list(migrations_dir.glob("*.sql"))
    assert len(sql_files) >= 1, "At least one migration file must exist in supabase/migrations/"

    for f in sql_files:
        # Standard Supabase timestamp format: YYYYMMDDHHMMSS_name.sql
        assert re.match(r"^\d{14}_[\w\-]+\.sql$", f.name), (
            f"Migration file {f.name} does not match format YYYYMMDDHHMMSS_name.sql"
        )


def test_no_duplicate_backend_migrations_directory():
    backend_migrations = Path(__file__).resolve().parent.parent / "migrations"
    assert not backend_migrations.exists(), (
        "Duplicate backend/migrations directory must not exist; "
        "use supabase/migrations/ as the canonical location"
    )


def test_migration_schema_and_security_content():
    migrations_dir = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
    migration_file = next(migrations_dir.glob("*_phase1_projects_and_media.sql"))
    content = migration_file.read_text(encoding="utf-8")

    # Table schemas
    assert "CREATE TABLE IF NOT EXISTS projects" in content
    assert "CREATE TABLE IF NOT EXISTS media" in content
    assert "CREATE TABLE IF NOT EXISTS analyses" in content

    # Foreign keys with cascade
    assert "REFERENCES projects(id) ON DELETE CASCADE" in content
    assert "REFERENCES media(id) ON DELETE CASCADE" in content

    # Indexes
    assert "CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id)" in content
    assert "CREATE INDEX IF NOT EXISTS idx_media_user_id ON media(user_id)" in content
    assert "CREATE INDEX IF NOT EXISTS idx_media_expires_at ON media(expires_at)" in content

    # Row Level Security
    assert "ALTER TABLE projects ENABLE ROW LEVEL SECURITY;" in content
    assert "ALTER TABLE media ENABLE ROW LEVEL SECURITY;" in content
    assert "ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;" in content

    # Grants
    assert "GRANT ALL ON TABLE projects TO authenticated, service_role;" in content
    assert "GRANT ALL ON TABLE media TO authenticated, service_role;" in content
    assert "GRANT ALL ON TABLE analyses TO authenticated, service_role;" in content

    # RLS user-scoping policies
    assert "auth.uid() = user_id" in content


def test_supabase_config_toml_settings():
    config_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "config.toml"
    assert config_path.is_file(), "supabase/config.toml must exist"
    content = config_path.read_text(encoding="utf-8")

    assert 'project_id = "fhfkjviishfvfyawfckh"' in content
    assert "enable_anonymous_sign_ins = true" in content
    assert 'file_size_limit = "100MiB"' in content
    # Ensure no hardcoded raw secret passwords/keys
    assert "secret_password" not in content.lower()
    assert "service_role_key =" not in content
