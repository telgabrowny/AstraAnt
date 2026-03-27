"""AstraAnt 3D interactive simulation GUI powered by Ursina."""


def launch(asteroid: str = "bennu", workers: int = 20, taskmasters: int = 1,
           couriers: int = 1, track: str = "a"):
    """Launch the 3D simulation window."""
    from .app import run_app
    run_app(asteroid=asteroid, workers=workers, taskmasters=taskmasters,
            couriers=couriers, track=track)
