-- Regle 1 : chaque transaction a au moins 2 ecritures et debits = credits.
CREATE OR REPLACE FUNCTION check_transaction_balanced() RETURNS trigger AS $$
DECLARE
    tx_id   integer := COALESCE(NEW.transaction_id, OLD.transaction_id);
    debits  bigint;
    credits bigint;
    n       integer;
BEGIN
    SELECT COALESCE(SUM(amount_cents) FILTER (WHERE direction = 'debit'), 0),
           COALESCE(SUM(amount_cents) FILTER (WHERE direction = 'credit'), 0),
           COUNT(*)
      INTO debits, credits, n
      FROM entries
     WHERE transaction_id = tx_id;

    IF n > 0 AND (n < 2 OR debits <> credits) THEN
        RAISE EXCEPTION 'unbalanced transaction %: debits % <> credits % (% entries)',
            tx_id, debits, credits, n
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entries_balanced ON entries;
CREATE CONSTRAINT TRIGGER trg_entries_balanced
    AFTER INSERT OR UPDATE OR DELETE ON entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION check_transaction_balanced();

-- Regle 2 : le ledger est en ajout seul. On corrige par une transaction inverse.
CREATE OR REPLACE FUNCTION forbid_ledger_changes() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ledger rows are immutable (% on %): use a reversal',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_entries_immutable ON entries;
CREATE TRIGGER trg_entries_immutable
    BEFORE UPDATE OR DELETE ON entries
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_changes();

DROP TRIGGER IF EXISTS trg_transactions_immutable ON transactions;
CREATE TRIGGER trg_transactions_immutable
    BEFORE UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_changes();
