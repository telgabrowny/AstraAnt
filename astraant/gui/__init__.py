"""AstraAnt 3D interactive simulation GUI powered by Ursina."""


def launch(asteroid: str = "bennu", workers: int = 20, taskmasters: int = 1,
           couriers: int = 2, track: str = "mechanical", **kwargs):
    """Launch the 3D simulation window."""
    from .app import run_app
    run_app(asteroid=asteroid, workers=workers, taskmasters=taskmasters,
            surface_ants=couriers, track=track)
