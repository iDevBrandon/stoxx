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

CREATE TABLE dividend_analysis (
ticker VARCHAR(10) PRIMARY KEY,
name VARCHAR(255) NOT NULL,
country VARCHAR(3) NOT NULL,
dividend_cagr_3yr DECIMAL(6,4),
dividend_cagr_5yr DECIMAL(6,4),
dividend_cagr_10yr DECIMAL(6,4),
total_dividends_history JSONB,
updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- add index
CREATE INDEX idx_dividend_analysis_country ON dividend_analysis(country);
CREATE INDEX idx_dividend_analysis_5yr_cagr ON dividend_analysis(dividend_cagr_5yr);
CREATE INDEX idx_dividend_analysis_updated_at ON dividend_analysis(updated_at);
