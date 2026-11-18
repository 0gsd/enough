"""enough's HTTP routes, one module per group (0.8, lane W2-SV): `enough/server.py`'s `create_app` builds
the app, its middleware, startup and shutdown and the static mount, then includes these routers in order.
Each module's `build_router(ctx)` is the old factory's code for that group, moved unchanged."""
