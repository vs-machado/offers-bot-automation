"""Shared catalog of NVIDIA Build models verified for offer parsing."""

LIGHTNING = "nvidia/nemotron-3.5-lightning-30b-a3b"
LAGUNA = "poolside/laguna-xs-2.1"
DEFAULT_MODELS = (LIGHTNING, LAGUNA)
CONFIG_TYPE = "nvidia_models"
MODELS = {
    LIGHTNING: "Nemotron 3.5 Lightning",
    LAGUNA: "Laguna XS 2.1",
    "nvidia/nemotron-3.5-bolt-e4b": "Nemotron 3.5 Bolt",
    "nvidia/nemotron-3.5-super-vl-120b-a12b": "Nemotron 3.5 Super VL",
}


def validate_models(data: object) -> tuple[str, str]:
    """Accept only distinct model IDs from the approved parser catalog."""
    if not isinstance(data, dict):
        raise ValueError("Selecione dois modelos NVIDIA disponíveis.")
    primary, secondary = data.get("primary"), data.get("secondary")
    if (
        not isinstance(primary, str)
        or not isinstance(secondary, str)
        or primary not in MODELS
        or secondary not in MODELS
        or primary == secondary
    ):
        raise ValueError("Selecione dois modelos NVIDIA disponíveis e diferentes.")
    return primary, secondary
