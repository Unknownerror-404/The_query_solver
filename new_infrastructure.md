# TODO: New infrastructure for uni‑to‑industry solution routing
# 1. Add a new DB table `solution_classifications` to store the classifier output.
# 2. Create a new table `industry_partner_categories` (if not already present) to map partners to category vectors.

# 3. Define a new model `SolutionClassifier` (in a new file `classifier.py`) that loads a sklearn LinearSVC or SGDClassifier and exposes 
#    def classify(text: str) -> str:  # returns a category label.

# 4. Add an API endpoint in `app_fastapi.py`:
#    @router.post("/university/{uni_id}/solutions/{sol_id}/classify") -> calls the classifier with the solution text, stores the label in `solution_classifications`, then 
#    looks up matching industry partners where partner.category == label and assigns the solution to the first available partner (or returns a list of candidates).

# 5. Create a helper in `storage.py`:
#    def assign_solution_to_partner(solution_id: int, partner_id: int) -> None
#    def load_solution(solution_id) -> dict
#    def load_partner_categories() -> Dict[str, List[int]]  # mapping from category to partner ids.

# 6. In `templates/industry.html` or a new component, provide a page for industry partners to see classified solutions assigned to them.

# 7. Update `requirements.txt` to include scikit‑learn if not present.
