class ServiceAppsRouter:
    """
    Routes merged "microservice apps" to dedicated databases.

    - Bettors.DemoMoney model stays on `demomoney`
    - Betdata app uses `betdata`
    - Analytics app uses `analytics`
    """

    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label
        model_name = model._meta.model_name

        if app_label == "Bettors" and model_name == "demomoney":
            return "demomoney"
        if app_label == "Betdata":
            return "betdata"
        if app_label == "Analytics":
            return "analytics"
        return None

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "Bettors" and model_name == "demomoney":
            return db == "demomoney"

        if app_label == "Betdata":
            return db == "betdata"

        if app_label == "Analytics":
            return db == "analytics"

        if db in {"betdata", "analytics", "demomoney"}:
            return False

        return None

