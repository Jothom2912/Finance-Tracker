describe("Budget page E2E", () => {
  const categories = [
    { idCategory: 9, name: "madvarer/dagligvarer", type: "expense" },
    { idCategory: 11, name: "transport", type: "expense" },
    { idCategory: 23, name: "boligstøtte", type: "income" },
  ];

  it("adds lines and saves a monthly budget", () => {
    cy.intercept("GET", "**/api/v1/categories/**", categories).as("getCategories");
    cy.intercept("GET", "**/api/v1/monthly-budgets/?month=*&year=*", {
      statusCode: 200,
      body: null,
    }).as("getBudget");
    cy.intercept("GET", "**/api/v1/monthly-budgets/summary?month=*&year=*", {
      statusCode: 200,
      body: {
        month: 2,
        year: 2026,
        budget_id: null,
        items: [],
        total_budget: 0,
        total_spent: 0,
        total_remaining: 0,
        over_budget_count: 0,
      },
    }).as("getSummary");

    cy.intercept("POST", "**/api/v1/monthly-budgets/", (req) => {
      expect(req.body.lines).to.have.length(2);
      expect(req.body.lines[0]).to.deep.equal({ category_id: 9, amount: 3000 });
      expect(req.body.lines[1]).to.deep.equal({ category_id: 11, amount: 1500 });

      req.reply({
        statusCode: 201,
        body: {
          id: 77,
          month: req.body.month,
          year: req.body.year,
          lines: [
            { id: 1, category_id: 9, category_name: "madvarer/dagligvarer", amount: 3000 },
            { id: 2, category_id: 11, category_name: "transport", amount: 1500 },
          ],
          total_budget: 4500,
          created_at: "2026-02-26T11:00:00",
        },
      });
    }).as("createBudget");

    // After save, page reloads budget + summary data.
    cy.intercept("GET", "**/api/v1/monthly-budgets/?month=*&year=*", {
      statusCode: 200,
      body: {
        id: 77,
        month: 2,
        year: 2026,
        lines: [
          { id: 1, category_id: 9, category_name: "madvarer/dagligvarer", amount: 3000 },
          { id: 2, category_id: 11, category_name: "transport", amount: 1500 },
        ],
        total_budget: 4500,
        created_at: "2026-02-26T11:00:00",
      },
    }).as("getBudgetAfterSave");
    cy.intercept("GET", "**/api/v1/monthly-budgets/summary?month=*&year=*", {
      statusCode: 200,
      body: {
        month: 2,
        year: 2026,
        budget_id: 77,
        items: [
          {
            category_id: 9,
            category_name: "madvarer/dagligvarer",
            budget_amount: 3000,
            spent_amount: 2100,
            remaining_amount: 900,
            percentage_used: 70,
          },
          {
            category_id: 11,
            category_name: "transport",
            budget_amount: 1500,
            spent_amount: 1200,
            remaining_amount: 300,
            percentage_used: 80,
          },
        ],
        total_budget: 4500,
        total_spent: 3300,
        total_remaining: 1200,
        over_budget_count: 0,
      },
    }).as("getSummaryAfterSave");

    cy.visit("/budget", {
      onBeforeLoad(win) {
        win.localStorage.setItem("access_token", "test-token");
        win.localStorage.setItem("account_id", "1");
      },
    });

    cy.wait("@getCategories");
    cy.wait("@getBudget");
    cy.wait("@getSummary");

    cy.get("[data-cy='add-category-select']").select("madvarer/dagligvarer");
    cy.get("[data-cy='add-line-btn']").click();
    cy.get("[data-cy='amount-input-9']").clear().type("3000");

    cy.get("[data-cy='add-category-select']").select("transport");
    cy.get("[data-cy='add-line-btn']").click();
    cy.get("[data-cy='amount-input-11']").clear().type("1500");

    cy.get("[data-cy='save-budget-btn']").click();
    cy.wait("@createBudget");
    cy.wait("@getBudgetAfterSave");
    cy.wait("@getSummaryAfterSave");

    cy.get("[data-cy='budget-summary']").should("be.visible");
    cy.contains("Total budget").should("be.visible");
    cy.contains("4.500").should("be.visible");
    cy.get("[data-cy='budget-line-9']").should("be.visible");
    cy.get("[data-cy='budget-line-11']").should("be.visible");
  });
});
