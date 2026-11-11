"""OpenProcess — AI-assisted IT governance process studio."""

from .schema import ProcessSpec, Node, Flow, Lane, Raci
from .extract import extract, extract_rulebased, extract_with_llm
from .bpmn import to_bpmn_xml
from .govern import evaluate, rule_catalogue
from .classify import classify

__version__ = "1.0.0"

__all__ = [
    "ProcessSpec", "Node", "Flow", "Lane", "Raci",
    "extract", "extract_rulebased", "extract_with_llm",
    "to_bpmn_xml", "evaluate", "rule_catalogue", "classify",
]
