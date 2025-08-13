# Dividend Data Pipeline (Top 500 Global Companies)

This project collects, processes, and stores dividend data for the top 500 global companies using Supabase and Python.

## Workflow

### 1. Supabase Table Setup

- Create two tables: `equities` and `dividends`
- Define all columns, primary keys (PK), foreign keys (FK), and unique constraints

### 2. Python Environment Setup

- Install `supabase-py`:
  ```bash
  pip install supabase
  ```
  Add Supabase URL and API key to a .env file

Add .env to .gitignore

### 3. Prompt-Based Data Collection & Insertion

Use AI (e.g., Claude) to:

Read the CSV and extract the top 500 companies

Fetch raw dividend data using yfinance

Calculate yearly total dividends, 3yr/5yr/10yr CAGR, and 7-year consecutive growth

Insert or update the data into Supabase
