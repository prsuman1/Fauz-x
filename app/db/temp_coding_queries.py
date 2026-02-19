"""
Database queries for temporary pre-seeded coding assignments.
Used by /api/temp/* endpoints for frontend testing without LLM generation.
"""
import json
from typing import Any, Optional
from uuid import UUID

import asyncpg


TEMP_CODING_QUESTIONS = [
    {
        "job_type": "backend",
        "title": "REST API for Todo List (CRUD)",
        "category": "API Design",
        "difficulty": "easy",
        "problem_statement": (
            "Build a simple REST API for a Todo List application that supports "
            "Create, Read, Update, and Delete operations. Each todo item should "
            "have an id, title, description (optional), and completed status. "
            "The API should follow RESTful conventions and return appropriate "
            "HTTP status codes."
        ),
        "input_format": "HTTP requests with JSON body for POST/PUT endpoints",
        "output_format": "JSON responses with appropriate status codes",
        "constraints": [
            "Use in-memory storage (no database required)",
            "IDs should auto-increment starting from 1",
            "Title is required and must be non-empty",
            "Default completed status is false",
            "Return 404 for non-existent todo items",
        ],
        "examples": [
            {
                "input": "POST /todos {\"title\": \"Buy groceries\", \"description\": \"Milk, eggs, bread\"}",
                "output": "{\"id\": 1, \"title\": \"Buy groceries\", \"description\": \"Milk, eggs, bread\", \"completed\": false}",
                "explanation": "Creates a new todo item and returns it with auto-generated id",
            },
            {
                "input": "GET /todos",
                "output": "[{\"id\": 1, \"title\": \"Buy groceries\", \"description\": \"Milk, eggs, bread\", \"completed\": false}]",
                "explanation": "Returns all todo items as a JSON array",
            },
        ],
        "test_cases": [
            {"input": "POST /todos {\"title\": \"Test\"}", "expected_output": "201 Created with todo object", "description": "Create a todo", "is_hidden": False},
            {"input": "GET /todos/1", "expected_output": "200 with todo object", "description": "Get single todo", "is_hidden": False},
            {"input": "PUT /todos/1 {\"completed\": true}", "expected_output": "200 with updated todo", "description": "Update todo", "is_hidden": False},
            {"input": "DELETE /todos/1", "expected_output": "204 No Content", "description": "Delete todo", "is_hidden": False},
            {"input": "GET /todos/999", "expected_output": "404 Not Found", "description": "Get non-existent todo", "is_hidden": True},
        ],
        "starter_code": {
            "python": "from flask import Flask, request, jsonify\n\napp = Flask(__name__)\ntodos = []\nnext_id = 1\n\n# Implement CRUD endpoints here\n\n@app.route('/todos', methods=['GET'])\ndef get_todos():\n    pass\n\n@app.route('/todos/<int:todo_id>', methods=['GET'])\ndef get_todo(todo_id):\n    pass\n\n@app.route('/todos', methods=['POST'])\ndef create_todo():\n    pass\n\n@app.route('/todos/<int:todo_id>', methods=['PUT'])\ndef update_todo(todo_id):\n    pass\n\n@app.route('/todos/<int:todo_id>', methods=['DELETE'])\ndef delete_todo(todo_id):\n    pass\n\nif __name__ == '__main__':\n    app.run(debug=True)",
            "javascript": "const express = require('express');\nconst app = express();\napp.use(express.json());\n\nlet todos = [];\nlet nextId = 1;\n\n// Implement CRUD endpoints here\n\napp.get('/todos', (req, res) => {\n  // TODO\n});\n\napp.get('/todos/:id', (req, res) => {\n  // TODO\n});\n\napp.post('/todos', (req, res) => {\n  // TODO\n});\n\napp.put('/todos/:id', (req, res) => {\n  // TODO\n});\n\napp.delete('/todos/:id', (req, res) => {\n  // TODO\n});\n\napp.listen(3000, () => console.log('Server running on port 3000'));",
        },
        "solution_approach": "Use an in-memory array to store todos. Implement standard CRUD operations with proper HTTP status codes (201 for create, 200 for read/update, 204 for delete, 404 for not found).",
        "skills_tested": ["REST API Design", "HTTP Methods", "Status Codes", "CRUD Operations"],
        "estimated_time_minutes": 25,
        "hints": [
            "Remember to handle the case where the request body is missing the title field",
            "Use appropriate HTTP status codes: 201 for creation, 204 for deletion",
            "Consider what should happen when updating — should partial updates be allowed?",
        ],
    },
    {
        "job_type": "backend",
        "title": "URL Shortener Service",
        "category": "API Design",
        "difficulty": "easy",
        "problem_statement": (
            "Build a simple URL shortener service. The service should accept a long URL "
            "and return a shortened version. When the shortened URL is accessed, it should "
            "redirect to the original URL. Use a simple encoding scheme (e.g., base62 or "
            "incremental counter) to generate short codes."
        ),
        "input_format": "POST request with JSON body containing the original URL",
        "output_format": "JSON response with the short code and full shortened URL",
        "constraints": [
            "Use in-memory storage (no database required)",
            "Short codes should be unique",
            "Original URL must be a valid URL format",
            "Return 404 for non-existent short codes",
            "Short codes should be at least 6 characters",
        ],
        "examples": [
            {
                "input": "POST /shorten {\"url\": \"https://www.example.com/very/long/path\"}",
                "output": "{\"short_code\": \"abc123\", \"short_url\": \"http://localhost:3000/abc123\", \"original_url\": \"https://www.example.com/very/long/path\"}",
                "explanation": "Creates a short code for the given URL",
            },
            {
                "input": "GET /abc123",
                "output": "302 Redirect to https://www.example.com/very/long/path",
                "explanation": "Redirects to the original URL using the short code",
            },
        ],
        "test_cases": [
            {"input": "POST /shorten {\"url\": \"https://example.com\"}", "expected_output": "201 with short_code", "description": "Shorten a URL", "is_hidden": False},
            {"input": "GET /<short_code>", "expected_output": "302 redirect", "description": "Redirect to original", "is_hidden": False},
            {"input": "GET /nonexistent", "expected_output": "404 Not Found", "description": "Non-existent short code", "is_hidden": False},
            {"input": "POST /shorten {\"url\": \"not-a-url\"}", "expected_output": "400 Bad Request", "description": "Invalid URL", "is_hidden": True},
        ],
        "starter_code": {
            "python": "from flask import Flask, request, jsonify, redirect\nimport string\nimport random\n\napp = Flask(__name__)\nurl_store = {}  # short_code -> original_url\n\ndef generate_short_code(length=6):\n    \"\"\"Generate a random short code.\"\"\"\n    pass\n\n@app.route('/shorten', methods=['POST'])\ndef shorten_url():\n    pass\n\n@app.route('/<short_code>')\ndef redirect_url(short_code):\n    pass\n\nif __name__ == '__main__':\n    app.run(debug=True)",
            "javascript": "const express = require('express');\nconst app = express();\napp.use(express.json());\n\nconst urlStore = {}; // short_code -> original_url\n\nfunction generateShortCode(length = 6) {\n  // TODO: Generate a random short code\n}\n\napp.post('/shorten', (req, res) => {\n  // TODO\n});\n\napp.get('/:shortCode', (req, res) => {\n  // TODO\n});\n\napp.listen(3000, () => console.log('Server running on port 3000'));",
        },
        "solution_approach": "Use a dictionary/map to store URL mappings. Generate random alphanumeric codes. Validate URLs before shortening. Use HTTP 302 redirect for short code lookups.",
        "skills_tested": ["API Design", "URL Handling", "Redirects", "Input Validation"],
        "estimated_time_minutes": 25,
        "hints": [
            "Use string.ascii_letters + string.digits for base62 encoding",
            "Check for duplicate short codes before storing",
            "Use a simple URL validation (check for http:// or https:// prefix)",
        ],
    },
    {
        "job_type": "frontend",
        "title": "Interactive Counter Component",
        "category": "React Components",
        "difficulty": "easy",
        "problem_statement": (
            "Build an interactive counter component in React. The counter should display "
            "a number and have buttons to increment, decrement, and reset the count. "
            "Add visual feedback — the number should turn green when positive, red when "
            "negative, and black when zero. Include a step size input that lets the user "
            "change how much the counter increments/decrements by."
        ),
        "input_format": "User interactions (button clicks and input changes)",
        "output_format": "React component rendering a counter with controls",
        "constraints": [
            "Use React functional components with hooks",
            "Step size must be a positive integer (minimum 1)",
            "Counter has no upper or lower bounds",
            "Reset sets counter to 0 and step size to 1",
            "Display the current step size",
        ],
        "examples": [
            {
                "input": "Initial render",
                "output": "Counter shows 0 (black text), step size is 1, increment/decrement/reset buttons visible",
                "explanation": "Default state when component mounts",
            },
            {
                "input": "Click increment 3 times with step=2",
                "output": "Counter shows 6 (green text)",
                "explanation": "3 increments × step size 2 = 6",
            },
        ],
        "test_cases": [
            {"input": "Click increment", "expected_output": "Counter shows 1", "description": "Basic increment", "is_hidden": False},
            {"input": "Click decrement from 0", "expected_output": "Counter shows -1 in red", "description": "Negative number styling", "is_hidden": False},
            {"input": "Set step=5, click increment", "expected_output": "Counter shows 5", "description": "Custom step size", "is_hidden": False},
            {"input": "Click reset", "expected_output": "Counter shows 0, step resets to 1", "description": "Reset functionality", "is_hidden": True},
        ],
        "starter_code": {
            "javascript": "import React, { useState } from 'react';\n\nfunction Counter() {\n  const [count, setCount] = useState(0);\n  const [step, setStep] = useState(1);\n\n  // TODO: Implement increment, decrement, reset handlers\n  // TODO: Add color logic based on count value\n\n  return (\n    <div style={{ textAlign: 'center', padding: '20px' }}>\n      <h1>Counter</h1>\n      {/* TODO: Display count with dynamic color */}\n      {/* TODO: Add increment, decrement, reset buttons */}\n      {/* TODO: Add step size input */}\n    </div>\n  );\n}\n\nexport default Counter;",
        },
        "solution_approach": "Use useState for count and step values. Compute text color with a simple conditional (positive=green, negative=red, zero=black). Handle step input validation to ensure positive integers.",
        "skills_tested": ["React Hooks", "State Management", "Event Handling", "Conditional Styling"],
        "estimated_time_minutes": 20,
        "hints": [
            "Use inline styles or CSS classes for dynamic coloring",
            "parseInt the step input and clamp to minimum of 1",
            "Remember to handle the reset for both count AND step size",
        ],
    },
    {
        "job_type": "frontend",
        "title": "Filterable Product List",
        "category": "React Components",
        "difficulty": "easy",
        "problem_statement": (
            "Build a filterable product list component in React. Display a list of products "
            "with name, category, and price. Include a search bar to filter by name and a "
            "category dropdown to filter by category. Both filters should work together. "
            "Show the count of matching products. Use the provided sample product data."
        ),
        "input_format": "User interactions (text input and dropdown selection)",
        "output_format": "React component rendering a filtered list of products",
        "constraints": [
            "Use React functional components with hooks",
            "Search should be case-insensitive",
            "Category filter options: All, Electronics, Clothing, Books, Food",
            "Both filters must work simultaneously",
            "Show 'No products found' when filters match nothing",
            "Display product count (e.g., 'Showing 3 of 10 products')",
        ],
        "examples": [
            {
                "input": "Search: 'shirt', Category: 'All'",
                "output": "Shows products with 'shirt' in the name from all categories",
                "explanation": "Text search filters across all categories",
            },
            {
                "input": "Search: '', Category: 'Electronics'",
                "output": "Shows only electronics products",
                "explanation": "Category filter without text search",
            },
        ],
        "test_cases": [
            {"input": "Initial render", "expected_output": "All products displayed with count", "description": "Show all products", "is_hidden": False},
            {"input": "Type 'laptop' in search", "expected_output": "Only matching products shown", "description": "Text filter", "is_hidden": False},
            {"input": "Select 'Books' category", "expected_output": "Only books shown", "description": "Category filter", "is_hidden": False},
            {"input": "Search 'xyz' (no match)", "expected_output": "'No products found' message", "description": "Empty results", "is_hidden": True},
        ],
        "starter_code": {
            "javascript": "import React, { useState } from 'react';\n\nconst PRODUCTS = [\n  { id: 1, name: 'Laptop', category: 'Electronics', price: 999 },\n  { id: 2, name: 'T-Shirt', category: 'Clothing', price: 29 },\n  { id: 3, name: 'JavaScript Book', category: 'Books', price: 49 },\n  { id: 4, name: 'Headphones', category: 'Electronics', price: 79 },\n  { id: 5, name: 'Jeans', category: 'Clothing', price: 59 },\n  { id: 6, name: 'React Cookbook', category: 'Books', price: 39 },\n  { id: 7, name: 'Keyboard', category: 'Electronics', price: 129 },\n  { id: 8, name: 'Green Tea', category: 'Food', price: 12 },\n  { id: 9, name: 'Hoodie', category: 'Clothing', price: 45 },\n  { id: 10, name: 'Dark Chocolate', category: 'Food', price: 8 },\n];\n\nconst CATEGORIES = ['All', 'Electronics', 'Clothing', 'Books', 'Food'];\n\nfunction ProductList() {\n  const [search, setSearch] = useState('');\n  const [category, setCategory] = useState('All');\n\n  // TODO: Filter products based on search and category\n  // TODO: Render search input, category dropdown, product list, and count\n\n  return (\n    <div style={{ padding: '20px', maxWidth: '600px', margin: '0 auto' }}>\n      <h1>Product List</h1>\n      {/* TODO: Add search input */}\n      {/* TODO: Add category dropdown */}\n      {/* TODO: Show product count */}\n      {/* TODO: Render filtered product list */}\n    </div>\n  );\n}\n\nexport default ProductList;",
        },
        "solution_approach": "Use useState for search text and category selection. Filter the products array using both criteria simultaneously. Use Array.filter with case-insensitive name matching and category check (skip category check if 'All').",
        "skills_tested": ["React Hooks", "Array Filtering", "Controlled Components", "UI State Management"],
        "estimated_time_minutes": 25,
        "hints": [
            "Use .toLowerCase() for case-insensitive search matching",
            "Chain filter conditions: name match AND (category === 'All' OR category matches)",
            "useMemo can optimize filtering if the product list is large",
        ],
    },
    {
        "job_type": "fullstack",
        "title": "Simple Notes App (React + API)",
        "category": "Full Stack",
        "difficulty": "easy",
        "problem_statement": (
            "Build a simple notes application with a React frontend and a REST API backend. "
            "Users should be able to create, view, and delete notes. Each note has a title "
            "and content. The frontend should display notes in a list and have a form to add "
            "new notes. The backend should store notes in memory and expose CRUD endpoints."
        ),
        "input_format": "Frontend: user interactions; Backend: HTTP requests with JSON",
        "output_format": "Frontend: rendered React UI; Backend: JSON responses",
        "constraints": [
            "Backend: Use Express.js or Flask with in-memory storage",
            "Frontend: Use React with functional components",
            "Notes must have title (required) and content (required)",
            "Display notes sorted by newest first",
            "Show confirmation before deleting a note",
            "Handle API errors gracefully in the frontend",
        ],
        "examples": [
            {
                "input": "Submit form with title='Meeting Notes', content='Discuss Q2 goals'",
                "output": "Note appears at top of list, form clears",
                "explanation": "Creating a new note adds it to the list and resets the form",
            },
            {
                "input": "Click delete on a note, confirm deletion",
                "output": "Note is removed from the list",
                "explanation": "Deleting a note removes it from both frontend and backend",
            },
        ],
        "test_cases": [
            {"input": "Create a note via form", "expected_output": "Note appears in list", "description": "Add note flow", "is_hidden": False},
            {"input": "GET /api/notes", "expected_output": "200 with array of notes", "description": "API list notes", "is_hidden": False},
            {"input": "Delete a note", "expected_output": "Note removed from list", "description": "Delete flow", "is_hidden": False},
            {"input": "Submit form without title", "expected_output": "Validation error shown", "description": "Form validation", "is_hidden": True},
        ],
        "starter_code": {
            "javascript": "// === Backend (server.js) ===\nconst express = require('express');\nconst cors = require('cors');\nconst app = express();\napp.use(cors());\napp.use(express.json());\n\nlet notes = [];\nlet nextId = 1;\n\n// TODO: Implement GET /api/notes\n// TODO: Implement POST /api/notes\n// TODO: Implement DELETE /api/notes/:id\n\napp.listen(3001, () => console.log('API running on port 3001'));\n\n// === Frontend (App.js) ===\nimport React, { useState, useEffect } from 'react';\n\nfunction App() {\n  const [notes, setNotes] = useState([]);\n  const [title, setTitle] = useState('');\n  const [content, setContent] = useState('');\n\n  // TODO: Fetch notes on mount\n  // TODO: Implement addNote function\n  // TODO: Implement deleteNote function\n\n  return (\n    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>\n      <h1>Notes App</h1>\n      {/* TODO: Add note form */}\n      {/* TODO: Notes list */}\n    </div>\n  );\n}\n\nexport default App;",
            "python": "# === Backend (app.py) ===\nfrom flask import Flask, request, jsonify\nfrom flask_cors import CORS\n\napp = Flask(__name__)\nCORS(app)\n\nnotes = []\nnext_id = 1\n\n# TODO: Implement GET /api/notes\n# TODO: Implement POST /api/notes\n# TODO: Implement DELETE /api/notes/<id>\n\nif __name__ == '__main__':\n    app.run(port=3001, debug=True)",
        },
        "solution_approach": "Backend: Create simple REST endpoints with in-memory list storage. Frontend: Use useEffect to fetch notes on mount, implement form submission with fetch/axios POST, and delete with confirmation dialog.",
        "skills_tested": ["React", "REST API", "Frontend-Backend Integration", "State Management", "CRUD Operations"],
        "estimated_time_minutes": 35,
        "hints": [
            "Use useEffect with an empty dependency array to fetch notes on mount",
            "Remember to set Content-Type: application/json in fetch requests",
            "Use window.confirm() for delete confirmation",
        ],
    },
    {
        "job_type": "fullstack",
        "title": "User Registration Form with Validation",
        "category": "Full Stack",
        "difficulty": "easy",
        "problem_statement": (
            "Build a user registration form with client-side and server-side validation. "
            "The form collects username, email, and password. Client-side validation should "
            "check for required fields, email format, and password strength. Server-side "
            "should re-validate and check for duplicate usernames/emails. Display validation "
            "errors inline next to each field."
        ),
        "input_format": "Frontend: form input; Backend: POST request with JSON body",
        "output_format": "Frontend: form with validation messages; Backend: JSON success/error response",
        "constraints": [
            "Username: 3-20 characters, alphanumeric only",
            "Email: valid email format",
            "Password: minimum 8 characters, at least one uppercase, one lowercase, one number",
            "All fields are required",
            "Show validation errors as user types (debounced or on blur)",
            "Server returns 400 with field-specific errors for validation failures",
        ],
        "examples": [
            {
                "input": "Submit with username='ab', email='invalid', password='weak'",
                "output": "Three validation errors displayed inline: 'Username must be at least 3 characters', 'Invalid email format', 'Password must contain at least one uppercase letter, one number'",
                "explanation": "Client-side validation catches all three errors before submission",
            },
            {
                "input": "Submit valid form: username='john123', email='john@example.com', password='Secure1pass'",
                "output": "Success message: 'Registration successful!'",
                "explanation": "All validations pass, server creates the user",
            },
        ],
        "test_cases": [
            {"input": "Submit empty form", "expected_output": "All required field errors shown", "description": "Required validation", "is_hidden": False},
            {"input": "Enter invalid email 'abc'", "expected_output": "Email format error shown", "description": "Email validation", "is_hidden": False},
            {"input": "Enter weak password '12345'", "expected_output": "Password strength errors", "description": "Password validation", "is_hidden": False},
            {"input": "Submit valid form", "expected_output": "Success response from server", "description": "Successful registration", "is_hidden": True},
        ],
        "starter_code": {
            "javascript": "// === Backend (server.js) ===\nconst express = require('express');\nconst cors = require('cors');\nconst app = express();\napp.use(cors());\napp.use(express.json());\n\nconst users = []; // In-memory user store\n\napp.post('/api/register', (req, res) => {\n  // TODO: Validate and register user\n});\n\napp.listen(3001, () => console.log('API running on port 3001'));\n\n// === Frontend (App.js) ===\nimport React, { useState } from 'react';\n\nfunction RegistrationForm() {\n  const [formData, setFormData] = useState({ username: '', email: '', password: '' });\n  const [errors, setErrors] = useState({});\n\n  // TODO: Implement validation logic\n  // TODO: Implement form submission\n\n  return (\n    <div style={{ padding: '20px', maxWidth: '400px', margin: '0 auto' }}>\n      <h1>Register</h1>\n      {/* TODO: Username field with error display */}\n      {/* TODO: Email field with error display */}\n      {/* TODO: Password field with error display */}\n      {/* TODO: Submit button */}\n    </div>\n  );\n}\n\nexport default RegistrationForm;",
            "python": "# === Backend (app.py) ===\nimport re\nfrom flask import Flask, request, jsonify\nfrom flask_cors import CORS\n\napp = Flask(__name__)\nCORS(app)\n\nusers = []  # In-memory user store\n\n@app.route('/api/register', methods=['POST'])\ndef register():\n    # TODO: Validate and register user\n    pass\n\nif __name__ == '__main__':\n    app.run(port=3001, debug=True)",
        },
        "solution_approach": "Implement validation as a pure function that returns field-specific errors. Run on blur in the frontend. On submit, run client validation first, then POST to server. Server re-validates and checks for duplicates in the in-memory store.",
        "skills_tested": ["Form Handling", "Validation", "Error Display", "Client-Server Communication"],
        "estimated_time_minutes": 30,
        "hints": [
            "Use a regex like /^[a-zA-Z0-9]+$/ for alphanumeric username check",
            "Use a simple email regex: /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/",
            "Test password with separate checks: /[A-Z]/, /[a-z]/, /[0-9]/",
        ],
    },
]


async def ensure_temp_coding_table(pool: asyncpg.Pool) -> None:
    """Create the temp_coding_questions table and seed it if empty (idempotent)."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_coding_questions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_type TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'easy',
                problem_statement TEXT NOT NULL,
                input_format TEXT DEFAULT '',
                output_format TEXT DEFAULT '',
                constraints JSONB DEFAULT '[]',
                examples JSONB DEFAULT '[]',
                test_cases JSONB DEFAULT '[]',
                starter_code JSONB DEFAULT '{}',
                solution_approach TEXT DEFAULT '',
                skills_tested JSONB DEFAULT '[]',
                estimated_time_minutes INT DEFAULT 30,
                hints JSONB DEFAULT '[]',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Seed only if table is empty
        count = await conn.fetchval("SELECT COUNT(*) FROM temp_coding_questions")
        if count == 0:
            for q in TEMP_CODING_QUESTIONS:
                await conn.execute(
                    """
                    INSERT INTO temp_coding_questions
                        (job_type, title, category, difficulty, problem_statement,
                         input_format, output_format, constraints, examples, test_cases,
                         starter_code, solution_approach, skills_tested,
                         estimated_time_minutes, hints)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    """,
                    q["job_type"],
                    q["title"],
                    q["category"],
                    q["difficulty"],
                    q["problem_statement"],
                    q["input_format"],
                    q["output_format"],
                    json.dumps(q["constraints"]),
                    json.dumps(q["examples"]),
                    json.dumps(q["test_cases"]),
                    json.dumps(q["starter_code"]),
                    q["solution_approach"],
                    json.dumps(q["skills_tested"]),
                    q["estimated_time_minutes"],
                    json.dumps(q["hints"]),
                )
            print(f"Seeded {len(TEMP_CODING_QUESTIONS)} temp coding questions")


async def fetch_random_temp_question(pool: asyncpg.Pool, job_type: str) -> Optional[asyncpg.Record]:
    """
    Fetch a random pre-seeded question for the given job_type.
    Falls back to 'fullstack' for ai_ml, devops, other.
    """
    if job_type not in ("backend", "frontend", "fullstack"):
        job_type = "fullstack"

    return await pool.fetchrow(
        """
        SELECT id, job_type, title, category, difficulty, problem_statement,
               input_format, output_format, constraints, examples, test_cases,
               starter_code, solution_approach, skills_tested,
               estimated_time_minutes, hints
        FROM temp_coding_questions
        WHERE job_type = $1
        ORDER BY RANDOM()
        LIMIT 1
        """,
        job_type,
    )


async def fetch_temp_question_by_id(pool: asyncpg.Pool, question_id: UUID) -> Optional[asyncpg.Record]:
    """Fetch a single temp coding question by its UUID."""
    return await pool.fetchrow(
        """
        SELECT id, job_type, title, category, difficulty, problem_statement,
               input_format, output_format, constraints, examples, test_cases,
               starter_code, solution_approach, skills_tested,
               estimated_time_minutes, hints
        FROM temp_coding_questions
        WHERE id = $1
        """,
        question_id,
    )
