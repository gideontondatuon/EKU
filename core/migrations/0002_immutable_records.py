from django.db import migrations

FORWARD = """
CREATE FUNCTION eku_no_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Immutable record: update/delete forbidden'; END;
$$;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON core_auditlog FOR EACH ROW EXECUTE FUNCTION eku_no_mutation();
CREATE TRIGGER revision_immutable BEFORE UPDATE OR DELETE ON cashflow_transactionrevision FOR EACH ROW EXECUTE FUNCTION eku_no_mutation();
CREATE TRIGGER decision_immutable BEFORE UPDATE OR DELETE ON imports_verificationdecision FOR EACH ROW EXECUTE FUNCTION eku_no_mutation();
CREATE TRIGGER transaction_no_hard_delete BEFORE DELETE ON cashflow_cashflowtransaction FOR EACH ROW EXECUTE FUNCTION eku_no_mutation();
CREATE FUNCTION eku_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Publication immutable'; END IF;
  IF OLD.sealed OR NOT NEW.sealed OR (to_jsonb(OLD) - 'sealed') IS DISTINCT FROM (to_jsonb(NEW) - 'sealed')
  THEN RAISE EXCEPTION 'Publication immutable'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER version_immutable BEFORE UPDATE OR DELETE ON publications_publicationversion FOR EACH ROW EXECUTE FUNCTION eku_version_guard();
CREATE FUNCTION eku_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_sealed boolean;
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Projection immutable'; END IF;
  SELECT sealed INTO version_sealed FROM publications_publicationversion WHERE id = NEW.version_id;
  IF version_sealed THEN RAISE EXCEPTION 'Cannot append to sealed publication'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER projection_immutable BEFORE INSERT OR UPDATE OR DELETE ON publications_publishedcashflowaggregate FOR EACH ROW EXECUTE FUNCTION eku_projection_guard();
CREATE FUNCTION eku_pointer_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_sealed boolean;
BEGIN
  IF NEW.current_publication_version_id IS NOT NULL THEN
    SELECT sealed INTO version_sealed FROM publications_publicationversion WHERE id = NEW.current_publication_version_id;
    IF NOT version_sealed THEN RAISE EXCEPTION 'Cannot publish unsealed version'; END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER pointer_sealed BEFORE INSERT OR UPDATE ON core_systemsettings FOR EACH ROW EXECUTE FUNCTION eku_pointer_guard();
"""
REVERSE = """
DROP TRIGGER IF EXISTS pointer_sealed ON core_systemsettings;
DROP FUNCTION IF EXISTS eku_pointer_guard();
DROP TRIGGER IF EXISTS projection_immutable ON publications_publishedcashflowaggregate;
DROP FUNCTION IF EXISTS eku_projection_guard();
DROP TRIGGER IF EXISTS version_immutable ON publications_publicationversion;
DROP FUNCTION IF EXISTS eku_version_guard();
DROP TRIGGER IF EXISTS audit_immutable ON core_auditlog;
DROP TRIGGER IF EXISTS revision_immutable ON cashflow_transactionrevision;
DROP TRIGGER IF EXISTS decision_immutable ON imports_verificationdecision;
DROP TRIGGER IF EXISTS transaction_no_hard_delete ON cashflow_cashflowtransaction;
DROP FUNCTION IF EXISTS eku_no_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("cashflow", "0002_initial"),
        ("imports", "0001_initial"),
        ("publications", "0002_publicationversion_sealed"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
