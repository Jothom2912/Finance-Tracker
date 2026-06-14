from __future__ import annotations


class SagaDomainError(Exception):
    pass


class SagaNotFound(SagaDomainError):
    def __init__(self, saga_id: str) -> None:
        super().__init__(f"Saga {saga_id} not found")
        self.saga_id = saga_id


class SagaAlreadyCompleted(SagaDomainError):
    def __init__(self, saga_id: str) -> None:
        super().__init__(f"Saga {saga_id} is already completed")
        self.saga_id = saga_id


class SagaStepMismatch(SagaDomainError):
    def __init__(self, saga_id: str, expected_step: str, received_step: str) -> None:
        super().__init__(f"Saga {saga_id}: expected reply for step '{expected_step}', got '{received_step}'")
        self.saga_id = saga_id
        self.expected_step = expected_step
        self.received_step = received_step


class DuplicateSaga(SagaDomainError):
    def __init__(self, correlation_id: str) -> None:
        super().__init__(f"Saga with correlation_id '{correlation_id}' already exists")
        self.correlation_id = correlation_id


class UnknownSagaType(SagaDomainError):
    def __init__(self, saga_type: str) -> None:
        super().__init__(f"No saga definition registered for type '{saga_type}'")
        self.saga_type = saga_type
