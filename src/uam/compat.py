import inspect
import typing
from typing import Any


def patch_typing_eval_type() -> None:
    current = typing._eval_type  # type: ignore[attr-defined]
    parameters = inspect.signature(current).parameters
    if "prefer_fwd_module" in parameters:
        return

    def wrapper(
        value: Any,
        globalns: dict[str, Any] | None,
        localns: dict[str, Any] | None,
        type_params: Any = None,
        **extra: Any,
    ) -> Any:
        kwargs: dict[str, Any] = {}
        if "type_params" in parameters:
            kwargs["type_params"] = type_params
        for name in ("recursive_guard", "format", "owner", "parent_fwdref", "prefer_fwd_module"):
            if name in parameters and name in extra:
                kwargs[name] = extra[name]
        return current(value, globalns, localns, **kwargs)

    typing._eval_type = wrapper  # type: ignore[attr-defined]
