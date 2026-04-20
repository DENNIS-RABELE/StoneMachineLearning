from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("Betdata", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
DO $$
DECLARE
  round_col text;
BEGIN
  SELECT column_name
    INTO round_col
  FROM information_schema.columns
  WHERE table_schema = current_schema()
    AND table_name = 'client_bet'
    AND column_name IN ('game_round', 'game_round_id')
  ORDER BY CASE WHEN column_name = 'game_round' THEN 0 ELSE 1 END
  LIMIT 1;

  IF round_col IS NULL THEN
    RAISE EXCEPTION 'client_bet missing game round column';
  END IF;

  CREATE TABLE IF NOT EXISTS client_round_state (
    id smallint PRIMARY KEY DEFAULT 1,
    current_round_id integer NOT NULL DEFAULT 1,
    current_round_status varchar(16) NOT NULL DEFAULT 'OPEN',
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT client_round_state_singleton CHECK (id = 1)
  );

  INSERT INTO client_round_state (id)
  VALUES (1)
  ON CONFLICT (id) DO NOTHING;

  EXECUTE format($func$
    CREATE OR REPLACE FUNCTION close_stale_client_bets() RETURNS trigger AS $body$
    DECLARE
      current_round integer;
      current_status varchar(16);
      bet_round integer;
    BEGIN
      SELECT current_round_id, current_round_status
        INTO current_round, current_status
      FROM client_round_state
      WHERE id = 1;

      bet_round := NEW.%1$I;

      IF current_status = 'CLOSED' THEN
        IF bet_round <= current_round THEN
          NEW.status := 'CLOSED';
        END IF;
      ELSE
        IF bet_round < current_round THEN
          NEW.status := 'CLOSED';
        END IF;
      END IF;

      UPDATE client_bet
      SET status = 'CLOSED'
      WHERE status = 'OPEN'
        AND (
          (current_status = 'CLOSED' AND %1$I <= current_round)
          OR (current_status <> 'CLOSED' AND %1$I < current_round)
        );

      RETURN NEW;
    END;
    $body$ LANGUAGE plpgsql;
  $func$, round_col);

  DROP TRIGGER IF EXISTS trg_close_stale_client_bets ON client_bet;
  CREATE TRIGGER trg_close_stale_client_bets
    BEFORE INSERT OR UPDATE ON client_bet
    FOR EACH ROW
    EXECUTE FUNCTION close_stale_client_bets();
END $$;
            """,
            reverse_sql="""
DO $$
BEGIN
  DROP TRIGGER IF EXISTS trg_close_stale_client_bets ON client_bet;
  DROP FUNCTION IF EXISTS close_stale_client_bets();
  DROP TABLE IF EXISTS client_round_state;
END $$;
            """,
        ),
    ]
