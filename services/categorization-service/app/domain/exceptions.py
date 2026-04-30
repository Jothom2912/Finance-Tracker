"""Domain exceptions for the Categorization bounded context."""


class CategorizationException(Exception):
    pass


class CategoryNotFound(CategorizationException):
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Category with ID {category_id} not found")


class SubCategoryNotFound(CategorizationException):
    def __init__(self, subcategory_id: int):
        self.subcategory_id = subcategory_id
        super().__init__(f"SubCategory with ID {subcategory_id} not found")


class DuplicateCategoryName(CategorizationException):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Category '{name}' already exists")


class DuplicateSubCategoryName(CategorizationException):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"SubCategory '{name}' already exists")


class MerchantNotFound(CategorizationException):
    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        super().__init__(f"Merchant with ID {merchant_id} not found")
