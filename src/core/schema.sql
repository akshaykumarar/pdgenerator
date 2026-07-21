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

-- 2. Indexes for Query Optimization & Deduplication
-- Index for quick sorting and lookups by patient name
CREATE INDEX IF NOT EXISTS idx_patients_name 
    ON pdgenerator.patients(last_name, first_name);

-- Index for searching and filtering by date of birth
CREATE INDEX IF NOT EXISTS idx_patients_dob 
    ON pdgenerator.patients(dob);

-- GIN Index for deep, index-supported queries inside JSONB persona_data
CREATE INDEX IF NOT EXISTS idx_patients_persona_gin 
    ON pdgenerator.patients USING gin(persona_data);
