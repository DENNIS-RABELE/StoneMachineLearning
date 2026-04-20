class DemoMoneyRouter:
    """
    Route DemoMoney reads/writes/migrations to the DEMOMONEY database.
    """

    app_label = "Bettors"
    model_name = "demomoney"
    db_alias = "demomoney"

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.app_label and model._meta.model_name == self.model_name:
            return self.db_alias
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.app_label and model._meta.model_name == self.model_name:
            return self.db_alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label != self.app_label:
            return None

        if model_name == self.model_name:
            return db == self.db_alias

        if db == self.db_alias:
            return False

        return None
