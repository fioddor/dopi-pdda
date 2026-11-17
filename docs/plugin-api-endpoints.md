# Debian Observer plug-ins: API routers

How an analytical plug-in serves HTTP endpoints on the Debian Observer API.
Companion document of `release2.project.v0.4.md` §12.1 (API extensibility) and
ADR-022.

The mechanism's contract (entry-point group, mounting rules, collision error)
lives in the platform's `docs/design/module-contracts.md`. This document is for
the plug-in developer exposing a router.

## The router

A plug-in exports a **standard FastAPI `APIRouter`**, built in a module named
by its `[project.entry-points."debian_observer.api_routers"]` entry point:

```python
# dopi_pdda/api.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/coordinates/{d}/{r}/{a}/packages/{package}/dependencies")
def direct_dependencies(d: str, r: str, a: str, package: str,
                        components: str = "all"):
    """Direct dependencies of one package, walking up."""
    ...
```

There is no declaration record format: the entry point references a module
that builds a router, and the platform mounts the router object it receives.
The platform **never imports or depends on any plug-in**: it receives the
router through the entry point, so the dependency arrow stays plug-in →
platform, never the reverse.

## Rules the platform enforces

 1. **The component-list selector is shared vocabulary.**
    If your endpoint answers per coordinate, it accepts
    `?components=main+non-free-firmware` (default `all`) and **echoes the
    list in the response**. A result must never be readable as belonging
    to another list.
 2. **The coordinate prefix is the platform's.**
    `/coordinates/{d}/{r}/{a}` is reserved for per-coordinate resources;
    anything after it is the declaring plug-in's namespace.
 3. **Path collisions fail at startup.** Two routers with the same
    `(method, path)` template abort app startup with both declaring
    packages in the error. The platform never shadows silently: if two
    plug-ins need the same resource, that is a design conversation
    between their owners, not a mounting order.
 4. **Read-only perimeter.**
    `GET` is the whole verb set in R2. A plug-in that needs to *write*
    through the API does not have endpoints yet — talk to the platform
    owner first (an open decision, not a loophole).
 5. **The platform wraps your handlers.**
    Mounting applies the platform's observability perimeter (spans and
    metrics, release2 §13) around every handler, and the component-list
    echo is validated on every per-coordinate response.

## Lifecycle

 - **Install**: the plug-in's entry point is loaded at app startup; its
   routes appear in `/openapi.json` with your docstrings as summaries.
 - **Absent**: an uninstalled plug-in causes no failure. The app starts
   identically without it.
 - **Error**: a router that fails to build (import error, a route that
   collides) stops startup with the failing plug-in named.

## Testing your router

 - Unit: import your router module; assert the routes (verbs, paths,
   `components` parameter with default `"all"`).
 - Contract (platform-side, runs in the platform's CI against your
   installed plug-in): every exposed path is mounted, answers its
   `?components=` selector, echoes the list, and 404s cleanly for an
   unknown coordinate.