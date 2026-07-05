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


class InvalidCategoryType(CategorizationException):
    def __init__(self, value: str):
        self.value = value
        super().__init__(f"Invalid category type '{value}' — must be expense, income, or transfer")


class CategoryHasSubcategories(CategorizationException):
    def __init__(self, category_id: int, count: int):
        self.category_id = category_id
        self.count = count
        super().__init__(
            f"Category {category_id} still has {count} subcategories — delete or move them first"
        )


class SubCategoryInUse(CategorizationException):
    def __init__(self, subcategory_id: int, reason: str):
        self.subcategory_id = subcategory_id
        self.reason = reason
        super().__init__(f"SubCategory {subcategory_id} cannot be deleted: {reason}")


class MerchantNotFound(CategorizationException):
    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        super().__init__(f"Merchant with ID {merchant_id} not found")
