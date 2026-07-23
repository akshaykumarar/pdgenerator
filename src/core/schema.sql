-- PostgreSQL Database Schema for Clinical Data Generator
--
-- This script creates the required database schema, tables, indexes, and constraints.
-- Custom schema name can be changed by replacing 'pdgenerator' with your target schema.

CREATE SCHEMA IF NOT EXISTS pdgenerator;

-- 1. Create Patients Table
CREATE TABLE IF NOT EXISTS pdgenerator.patients (
    patient_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE,
    gender VARCHAR(50),
    persona_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Query Optimization & Deduplication
CREATE INDEX IF NOT EXISTS idx_patients_name 
    ON pdgenerator.patients(last_name, first_name);

CREATE INDEX IF NOT EXISTS idx_patients_dob 
    ON pdgenerator.patients(dob);

CREATE INDEX IF NOT EXISTS idx_patients_persona_gin 
    ON pdgenerator.patients USING gin(persona_data);


-- 2. Create Insurance Providers Table
CREATE TABLE IF NOT EXISTS pdgenerator.insurance_providers (
    provider_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    abbreviation VARCHAR(50),
    policy_url TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- 3. Create Insurance Plans Table
CREATE TABLE IF NOT EXISTS pdgenerator.insurance_plans (
    plan_id VARCHAR(100) PRIMARY KEY,
    provider_id VARCHAR(50) NOT NULL REFERENCES pdgenerator.insurance_providers(provider_id) ON DELETE CASCADE,
    plan_name VARCHAR(255) NOT NULL,
    plan_type VARCHAR(100) NOT NULL,
    policy_url TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_insurance_plans_provider 
    ON pdgenerator.insurance_plans(provider_id);

CREATE INDEX IF NOT EXISTS idx_insurance_plans_type 
    ON pdgenerator.insurance_plans(plan_type);


-- 4. Create CPT / HCPCS Code Mapping Table
CREATE TABLE IF NOT EXISTS pdgenerator.cpt_code_map (
    cpt_code VARCHAR(50) PRIMARY KEY,
    procedure_name TEXT NOT NULL,
    department VARCHAR(100),
    test_case VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast case-insensitive lookup by procedure name
CREATE INDEX IF NOT EXISTS idx_cpt_procedure_lower 
    ON pdgenerator.cpt_code_map (LOWER(procedure_name));
