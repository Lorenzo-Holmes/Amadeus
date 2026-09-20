"""One composition root shared by the CLI, migration drills and end-to-end runs."""
from __future__ import annotations
from dialogue_admission import DialogueAdmissionController
from chat import ChatService
from retrieval import RetrievalService
from runtime_store import RuntimeStore
from persona_growth import PersonaGrowthController
from transcript_store import TranscriptStore, SessionHandle

def open_chat(store: TranscriptStore, handle: SessionHandle, scope: dict) -> ChatService:
    controller = DialogueAdmissionController(store)
    runtime = RuntimeStore(store, controller)
    growth = PersonaGrowthController(runtime)
    acceptance={}
    if scope.get('formal_validation') or 'semantic_acceptance_binding' in scope:
        from semantic_binding import validate_binding,strict_selected
        from trusted_admission_adapter import TrustedAdmissionAdapter
        from accepted_output import SemanticAcceptance
        binding=validate_binding(scope.get('semantic_acceptance_binding'),scope)
        acceptance={'semantic_acceptance_mode':binding['semantic_acceptance_mode'],'semantic_acceptance_binding':binding,
                    'semantic_acceptance':SemanticAcceptance(TrustedAdmissionAdapter(binding) if strict_selected(binding) else None,
                                                            binding=binding)}
    return ChatService(store, handle, scope, memory_provider=RetrievalService(runtime, growth),
                       admission_controller=controller, growth_controller=growth,**acceptance)
