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
    return ChatService(store, handle, scope, memory_provider=RetrievalService(runtime, growth),
                       admission_controller=controller, growth_controller=growth)
