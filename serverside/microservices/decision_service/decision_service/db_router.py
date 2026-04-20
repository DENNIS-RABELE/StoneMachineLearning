class ServiceAppsRouter:
    """
    Routes merged "microservice apps" to dedicated databases.

    - Generator app uses `odds`
    - Gameplay app uses `unity`
    """

    def db_for_read(self, model, **hints):
        app_label = model._meta.app_label
        if app_label == "Generator":
            return "odds"
        if app_label == "Gameplay":
            return "unity"
        return None

    def db_for_write(self, model, **hints):
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "Generator":
            return db == "odds"
        if app_label == "Gameplay":
            return db == "unity"

        if db in {"odds", "unity"}:
            return False

        return None

