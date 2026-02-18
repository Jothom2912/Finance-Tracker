"""
Domain exceptions for Category bounded context.
These represent business rule violations.
"""


class CategoryException(Exception):
    """Base exception for category domain."""
    pass


class CategoryNotFound(CategoryException):
    """Raised when category doesn't exist."""
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Category with ID {category_id} not found")


class DuplicateCategoryName(CategoryException):
    """Raised when a category with the same name already exists."""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Kategori med dette navn eksisterer allerede.")


class DuplicateCategoryNameOnUpdate(CategoryException):
    """Raised when updating would create a duplicate name."""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"En anden kategori med dette navn eksisterer allerede.")
