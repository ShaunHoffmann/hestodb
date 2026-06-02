-- PostgreSQL schema for HESTO data platform.
-- Source of truth for schema definitions; update schema.mmd to match this file.
-- Uses the user's draft (Mission, People, Teams, Tech Awards, Technology, institutions)
-- as the foundation and extends it for report ingestion/analytics.

CREATE EXTENSION IF NOT EXISTS citext;

-- -----------------------------
-- Controlled vocabularies
-- -----------------------------
CREATE TYPE team_role AS ENUM ('principal_investigator', 'co_investigator', 'collaborator', 'student');
CREATE TYPE research_regime AS ENUM ('magnetosphere', 'itm', 'solar science', 'space weather', 'heliosphere');
CREATE TYPE award_id AS ENUM ('HTIDeS-LNAPP', 'HTIDeS-ITD', 'HFOS', 'LCAS', 'HESTO-Direct', 'HFORT', 'Explorer-Small', 'Explorer-Medium', 'Mission of Opportunity', 'Artemis');
CREATE TYPE trl_level AS ENUM ('1', '2', '3', '4', '5', '6', '7', '8', '9');
CREATE TYPE institution_category AS ENUM ('university', 'industry', 'government', 'federally_funded_research_center', 'non_profit', 'other');
CREATE TYPE spaceflight_platform AS ENUM ('sounding rocket', 'airborne', 'balloon', 'spacecraft', 'space station', 'lander');
CREATE TYPE spaceflight_destination AS ENUM ('low_earth_orbit', 'geostationary_orbit', 'moon', 'mars', 'deep_space', 'other');
CREATE TYPE award_type AS ENUM ('grant', 'contract', 'cooperative_agreement', 'other');
CREATE TYPE publication_type AS ENUM ('peer-reviewed journal', 'non-peer reviewed journal', 'conference presentation (oral)', 'conference presentation (poster)', 'web article', 'other');
-- -----------------------------
-- Foundation tables from user draft
-- -----------------------------

CREATE TABLE admin_people (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	first_name TEXT,
	last_name TEXT,
	email CITEXT,
	PRIMARY KEY (id),
	CONSTRAINT ck_admin_people_identity CHECK (first_name IS NOT NULL OR last_name IS NOT NULL OR email IS NOT NULL),
	UNIQUE (email)
)

CREATE TABLE hesto_taxonomy_lookup (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

CREATE TABLE institutions (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name_long TEXT NOT NULL,
	name_short TEXT,
	category institution_category DEFAULT 'other' NOT NULL,
	country VARCHAR(2) DEFAULT 'US' NOT NULL,
	address_zip TEXT CHECK (address_zip ~ '^[A-Za-z0-9][A-Za-z0-9 -]{1,14}[A-Za-z0-9]$'),
	PRIMARY KEY (id),
	CONSTRAINT ck_institutions_country CHECK (country ~ '^[A-Z]{2}$')
)

CREATE TABLE people (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	first_name TEXT,
	last_name TEXT,
	email CITEXT,
	institution_id BIGINT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_people_identity CHECK (first_name IS NOT NULL OR last_name IS NOT NULL OR email IS NOT NULL),
	UNIQUE (email),
	FOREIGN KEY(institution_id) REFERENCES institutions (id) ON DELETE RESTRICT
)

CREATE TABLE science_discipline_lookup (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

CREATE TABLE science_region_lookup (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

CREATE TABLE technology_category (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

CREATE TABLE emerging_technology_category_lookup (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)

CREATE TABLE us_state_lookup (
	state_code VARCHAR(2) NOT NULL,
	state_name TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (state_code),
	CONSTRAINT ck_us_state_lookup_state_code CHECK (state_code ~ '^[A-Z]{2}$'),
	UNIQUE (state_name)
)

CREATE TABLE mission (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_by_id BIGINT,
	edited_by_id BIGINT,
	edited_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name_long TEXT,
	name_short TEXT,
	abstract TEXT,
	award_id award_id,
	short_description TEXT,
	science_discipline_id BIGINT,
	science_region_id BIGINT,
	hesto_taxonomy_id BIGINT,
	spaceflight_destination spaceflight_destination,
	spaceflight_platform spaceflight_platform,
	selection_letter_url TEXT,
	pi_id BIGINT,
	launch_date DATE CONSTRAINT ck_mission_launch_date CHECK (launch_date IS NULL OR launch_date >= DATE '1957-10-04'),
	PRIMARY KEY (id),
	FOREIGN KEY(science_discipline_id) REFERENCES science_discipline_lookup (id) ON DELETE SET NULL,
	FOREIGN KEY(science_region_id) REFERENCES science_region_lookup (id) ON DELETE SET NULL,
	FOREIGN KEY(hesto_taxonomy_id) REFERENCES hesto_taxonomy_lookup (id) ON DELETE SET NULL,
	FOREIGN KEY(pi_id) REFERENCES people (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by_id) REFERENCES admin_people (id) ON DELETE SET NULL,
	FOREIGN KEY(edited_by_id) REFERENCES admin_people (id) ON DELETE SET NULL
)

CREATE TABLE zip_state_lookup (
	zip_code TEXT NOT NULL,
	state_code VARCHAR(2) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (zip_code),
	CONSTRAINT ck_zip_state_lookup_zip_code CHECK (zip_code ~ '^\d{5}(-\d{4})?$'),
	FOREIGN KEY(state_code) REFERENCES us_state_lookup (state_code) ON DELETE RESTRICT
)

CREATE TABLE technology (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_by_id BIGINT,
	edited_by_id BIGINT,
	edited_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name_long TEXT,
	name_short TEXT,
	overview TEXT,
	principle_of_operations TEXT,
	advantages_and_disadvantages TEXT,
	relevance_to_science TEXT,
	relevance_to_agency TEXT,
	relevance_to_country TEXT,
	mission_id BIGINT NOT NULL,
	trl_current trl_level,
	size_length NUMERIC CONSTRAINT ck_technology_size_length CHECK (size_length IS NULL OR size_length >= 0),
	size_width NUMERIC CONSTRAINT ck_technology_size_width CHECK (size_width IS NULL OR size_width >= 0),
	size_height NUMERIC CONSTRAINT ck_technology_size_height CHECK (size_height IS NULL OR size_height >= 0),
	volume NUMERIC GENERATED ALWAYS AS (size_length * size_width * size_height) STORED,
	power_average NUMERIC CONSTRAINT ck_technology_power_average CHECK (power_average IS NULL OR power_average >= 0),
	power_peak NUMERIC CONSTRAINT ck_technology_power_peak CHECK (power_peak IS NULL OR power_peak >= 0),
	data_rate_average NUMERIC CONSTRAINT ck_technology_data_rate_average CHECK (data_rate_average IS NULL OR data_rate_average >= 0),
	data_rate_peak NUMERIC CONSTRAINT ck_technology_data_rate_peak CHECK (data_rate_peak IS NULL OR data_rate_peak >= 0),
	mass NUMERIC CONSTRAINT ck_technology_mass CHECK (mass IS NULL OR mass >= 0),
	pointing_requirements TEXT,
	port_power TEXT,
	port_communication TEXT,
	power_voltage NUMERIC CONSTRAINT ck_technology_power_voltage CHECK (power_voltage IS NULL OR power_voltage >= 0),
	protocol_communication TEXT,
	special_power_considerations TEXT,
	requires_thermal_isolation BOOLEAN DEFAULT false NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by_id) REFERENCES admin_people (id) ON DELETE SET NULL,
	FOREIGN KEY(edited_by_id) REFERENCES admin_people (id) ON DELETE SET NULL,
	FOREIGN KEY(mission_id) REFERENCES mission (id) ON DELETE RESTRICT
)

CREATE TABLE awards (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_by_id BIGINT,
	edited_by_id BIGINT,
	edited_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	name TEXT,
	abstract TEXT,
	funding_source TEXT,
	solicitation_id TEXT,
	award_id award_id,
	pi_id BIGINT,
	technology_id BIGINT,
	total_award NUMERIC(14, 2) CONSTRAINT ck_awards_total_award CHECK (total_award IS NULL OR total_award >= 0),
	research_regime research_regime,
	award_type award_type,
	project_id TEXT,
	PRIMARY KEY (id),
	UNIQUE (award_id),
	FOREIGN KEY(pi_id) REFERENCES people (id) ON DELETE SET NULL,
	FOREIGN KEY(technology_id) REFERENCES technology (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by_id) REFERENCES admin_people (id) ON DELETE SET NULL,
	FOREIGN KEY(edited_by_id) REFERENCES admin_people (id) ON DELETE SET NULL,
	UNIQUE (project_id)
)

CREATE TABLE technology_category_map (
	technology_id BIGINT NOT NULL,
	category_id BIGINT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (technology_id, category_id),
	FOREIGN KEY(technology_id) REFERENCES technology (id) ON DELETE CASCADE,
	FOREIGN KEY(category_id) REFERENCES technology_category (id) ON DELETE RESTRICT
)

CREATE TABLE technology_emerging_technology_map (
	technology_id BIGINT NOT NULL,
	category_id BIGINT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (technology_id, category_id),
	FOREIGN KEY(technology_id) REFERENCES technology (id) ON DELETE CASCADE,
	FOREIGN KEY(category_id) REFERENCES emerging_technology_category_lookup (id) ON DELETE RESTRICT
)

CREATE TABLE technology_trl (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	technology_id BIGINT NOT NULL,
	report_id BIGINT NOT NULL,
	trl_value trl_level NOT NULL,
	trl_date DATE NOT NULL,
	note TEXT,
	justification TEXT,
	PRIMARY KEY (id),
	CONSTRAINT uq_technology_trl_technology_id_trl_date UNIQUE (technology_id, trl_date),
	FOREIGN KEY(technology_id) REFERENCES technology (id) ON DELETE CASCADE
)

CREATE TABLE reports (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	award_id BIGINT,
	filename TEXT NOT NULL,
	file_path TEXT NOT NULL,
	source_folder TEXT,
	report_year INTEGER CONSTRAINT ck_reports_report_year CHECK (report_year IS NULL OR report_year BETWEEN 2000 AND 2100),
	source_modified_at TIMESTAMP WITH TIME ZONE,
	extracted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	slide_count INTEGER CONSTRAINT ck_reports_slide_count CHECK (slide_count IS NULL OR slide_count >= 0),
	source_sha256 TEXT,
	PRIMARY KEY (id),
	CONSTRAINT ck_reports_file_path CHECK (length(trim(file_path)) > 0),
	FOREIGN KEY(award_id) REFERENCES awards (id) ON DELETE SET NULL
)

CREATE TABLE publications (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	report_id BIGINT NOT NULL,
	publication_type publication_type NOT NULL,
	title TEXT,
	publication_date DATE,
	citation TEXT,
	url TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE
)

CREATE TABLE patents (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	report_id BIGINT NOT NULL,
	patent_id TEXT NOT NULL,
	title TEXT,
	abstract TEXT,
	application_number TEXT,
	inventors TEXT,
	assignee TEXT,
	filing_date DATE,
	date_issued DATE,
	jurisdiction VARCHAR(2) DEFAULT 'US' NOT NULL,
	patent_url TEXT,
	status TEXT,
	PRIMARY KEY (id),
	CONSTRAINT ck_patents_date_sequence CHECK (date_issued IS NULL OR filing_date IS NULL OR date_issued >= filing_date),
	CONSTRAINT ck_patents_jurisdiction CHECK (jurisdiction ~ '^[A-Z]{2}$'),
	UNIQUE (patent_id),
	FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE
)

ALTER TABLE technology_trl
	ADD CONSTRAINT fk_technology_trl_report_id
	FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE

CREATE TABLE teams (
	id BIGINT GENERATED ALWAYS AS IDENTITY,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	people_id BIGINT NOT NULL,
	award_id BIGINT NOT NULL,
	role team_role DEFAULT 'co_investigator' NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_teams_people_award_role UNIQUE (people_id, award_id, role),
	FOREIGN KEY(people_id) REFERENCES people (id) ON DELETE CASCADE,
	FOREIGN KEY(award_id) REFERENCES awards (id) ON DELETE CASCADE
)

CREATE UNIQUE INDEX uq_institutions_name_long_ci ON institutions (lower(name_long))

CREATE INDEX idx_mission_award_id ON mission (award_id)

CREATE INDEX idx_mission_created_by_id ON mission (created_by_id)

CREATE INDEX idx_mission_edited_by_id ON mission (edited_by_id)

CREATE INDEX idx_mission_hesto_taxonomy_id ON mission (hesto_taxonomy_id)

CREATE INDEX idx_mission_pi_id ON mission (pi_id)

CREATE INDEX idx_mission_science_discipline_id ON mission (science_discipline_id)

CREATE INDEX idx_mission_science_region_id ON mission (science_region_id)

CREATE INDEX idx_technology_created_by_id ON technology (created_by_id)

CREATE INDEX idx_technology_edited_by_id ON technology (edited_by_id)

CREATE INDEX idx_technology_mission_id ON technology (mission_id)

CREATE INDEX idx_awards_pi_id ON awards (pi_id)

CREATE INDEX idx_awards_created_by_id ON awards (created_by_id)

CREATE INDEX idx_awards_edited_by_id ON awards (edited_by_id)

CREATE INDEX idx_awards_technology_id ON awards (technology_id)

CREATE INDEX idx_technology_category_map_category_id ON technology_category_map (category_id)

CREATE INDEX idx_technology_emerging_technology_map_category_id ON technology_emerging_technology_map (category_id)

CREATE INDEX idx_technology_trl_technology_date ON technology_trl (technology_id, trl_date DESC)

CREATE INDEX idx_technology_trl_report_id ON technology_trl (report_id)

CREATE INDEX idx_reports_award ON reports (award_id)

CREATE INDEX idx_reports_extracted_at ON reports (extracted_at DESC)

CREATE INDEX idx_publications_report_id ON publications (report_id)

CREATE INDEX idx_publications_publication_type ON publications (publication_type)

CREATE INDEX idx_patents_report_id ON patents (report_id)

CREATE INDEX idx_patents_date_issued ON patents (date_issued)

CREATE UNIQUE INDEX uq_reports_file_path ON reports (file_path)

CREATE UNIQUE INDEX uq_reports_filename_hash ON reports (filename, coalesce(source_sha256, ''))

INSERT INTO science_discipline_lookup (name)
VALUES
    ('earth science'),
    ('planetary science'),
    ('heliophysics'),
    ('astrophysics')
ON CONFLICT (name) DO NOTHING;

INSERT INTO science_region_lookup (name)
VALUES
    ('magnetosphere'),
    ('ionosphere/thermosphere/mesosphere'),
    ('solar science'),
    ('heliosphere')
ON CONFLICT (name) DO NOTHING;

INSERT INTO hesto_taxonomy_lookup (name)
VALUES
    ('fields - magnetic'),
    ('fields - electric'),
    ('particles - ions/protons'),
    ('particles - neutrals/neutrons'),
    ('particles - dust/debris'),
    ('photons - radio'),
    ('photons - microwave'),
    ('photons - infrared'),
    ('photons - visible'),
    ('photons - ultraviolet'),
    ('photons - extreme ultraviolet'),
    ('photons - x-ray'),
    ('photons - gamma-ray')
ON CONFLICT (name) DO NOTHING;

INSERT INTO emerging_technology_category_lookup (name)
VALUES
	('quantum sensing'),
	('nanotechnology'),
	("artificial intelligence/machine learning"),
	('additive manufacturing'),
	('microfabrication')
ON CONFLICT (name) DO NOTHING;

INSERT INTO us_state_lookup (state_code, state_name)
VALUES
    ('AL', 'Alabama'),
    ('AK', 'Alaska'),
    ('AZ', 'Arizona'),
    ('AR', 'Arkansas'),
    ('CA', 'California'),
    ('CO', 'Colorado'),
    ('CT', 'Connecticut'),
    ('DE', 'Delaware'),
    ('FL', 'Florida'),
    ('GA', 'Georgia'),
    ('HI', 'Hawaii'),
    ('ID', 'Idaho'),
    ('IL', 'Illinois'),
    ('IN', 'Indiana'),
    ('IA', 'Iowa'),
    ('KS', 'Kansas'),
    ('KY', 'Kentucky'),
    ('LA', 'Louisiana'),
    ('ME', 'Maine'),
    ('MD', 'Maryland'),
    ('MA', 'Massachusetts'),
    ('MI', 'Michigan'),
    ('MN', 'Minnesota'),
    ('MS', 'Mississippi'),
    ('MO', 'Missouri'),
    ('MT', 'Montana'),
    ('NE', 'Nebraska'),
    ('NV', 'Nevada'),
    ('NH', 'New Hampshire'),
    ('NJ', 'New Jersey'),
    ('NM', 'New Mexico'),
    ('NY', 'New York'),
    ('NC', 'North Carolina'),
    ('ND', 'North Dakota'),
    ('OH', 'Ohio'),
    ('OK', 'Oklahoma'),
    ('OR', 'Oregon'),
    ('PA', 'Pennsylvania'),
    ('RI', 'Rhode Island'),
    ('SC', 'South Carolina'),
    ('SD', 'South Dakota'),
    ('TN', 'Tennessee'),
    ('TX', 'Texas'),
    ('UT', 'Utah'),
    ('VT', 'Vermont'),
    ('VA', 'Virginia'),
    ('WA', 'Washington'),
    ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'),
    ('WY', 'Wyoming'),
    ('DC', 'District of Columbia')
ON CONFLICT (state_code) DO NOTHING;

CREATE OR REPLACE VIEW v_latest_report_per_project AS
    SELECT DISTINCT ON (ta.project_id)
        ta.project_id,
        r.id AS report_id,
        r.filename,
        r.extracted_at,
        r.source_modified_at
    FROM awards ta
    JOIN reports r ON r.award_id = ta.id
    WHERE ta.project_id IS NOT NULL
    ORDER BY ta.project_id, COALESCE(r.source_modified_at, r.extracted_at) DESC

CREATE OR REPLACE VIEW v_institutions_with_state AS
    SELECT
        i.id,
        i.created_at,
        i.name_long,
        i.name_short,
        i.category,
        i.country,
        i.address_zip,
        z.state_code,
        s.state_name
    FROM institutions i
    LEFT JOIN zip_state_lookup z
        ON i.country = 'US'
       AND substring(i.address_zip FROM '^\d{5}') = substring(z.zip_code FROM '^\d{5}')
    LEFT JOIN us_state_lookup s
        ON s.state_code = z.state_code
