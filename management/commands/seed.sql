
-- Ensure the uuid-ossp extension is enabled for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Insert seed data for Company
INSERT INTO app_management_company (name, email, phone_number, address, created_at, updated_at)
VALUES
('Company A', 'companya@example.com', '1234567890', '123 Street, City', NOW(), NOW()),
('Company B', 'companyb@example.com', '0987654321', '456 Avenue, City', NOW(), NOW());

-- Insert seed data for Customer
INSERT INTO app_management_customer (id, phone_number, address, created_at, updated_at, employer_id, user_id)
VALUES
(uuid_generate_v4(), '1234567890', '123 Street, City', NOW(), NOW(), (SELECT id FROM app_management_company WHERE name='Company A'), NULL),
(uuid_generate_v4(), '0987654321', '456 Avenue, City', NOW(), NOW(), (SELECT id FROM app_management_company WHERE name='Company B'), NULL);

-- Insert seed data for Operator
INSERT INTO app_management_operator (id, phone_number, address, created_at, updated_at, employer_id, user_id)
VALUES
(uuid_generate_v4(), '1234567890', '123 Street, City', NOW(), NOW(), (SELECT id FROM app_management_company WHERE name='Company A'), NULL),
(uuid_generate_v4(), '0987654321', '456 Avenue, City', NOW(), NOW(), (SELECT id FROM app_management_company WHERE name='Company B'), NULL);

-- Insert seed data for Machine
INSERT INTO app_management_machine (id, machine_number, machine_type, manufacturer, production_year, expiration_year, owner_id, created_at, updated_at)
VALUES
(uuid_generate_v4(), 'M123', 'Type A', 'Manufacturer A', '2020', '2030', (SELECT id FROM app_management_company WHERE name='Company A'), NOW(), NOW()),
(uuid_generate_v4(), 'M456', 'Type B', 'Manufacturer B', '2021', '2031', (SELECT id FROM app_management_company WHERE name='Company B'), NOW(), NOW());

-- Insert seed data for MachineParameter
INSERT INTO app_management_machineparameter (id, injection_temperature, mold_temperature, clamping_force, injection_pressure, cooling_time, velocity, hot_runner_temperature, decompression, rotation_speed_of_screw, hold_pressure, hold_velocity, hold_time, position, back_pressure, machine_id, created_at, updated_at)
VALUES
(uuid_generate_v4(), '200', '150', '500', '1000', '30', '50', '180', '10', '300', '800', '60', '20', '10', '5', (SELECT id FROM app_management_machine WHERE machine_number='M123'), NOW(), NOW()),
(uuid_generate_v4(), '210', '160', '600', '1100', '35', '55', '190', '15', '310', '810', '65', '25', '15', '10', (SELECT id FROM app_management_machine WHERE machine_number='M456'), NOW(), NOW());

-- Insert seed data for BugReport
INSERT INTO app_management_bugreport (customer_id, machine_id, operator_id, urgency, status, description, created_at, updated_at)
VALUES
((SELECT id FROM app_management_customer LIMIT 1), (SELECT id FROM app_management_machine LIMIT 1), (SELECT id FROM app_management_operator LIMIT 1), 'Urgent', 'Not yet', 'Description of the bug', NOW(), NOW()),
((SELECT id FROM app_management_customer OFFSET 1 LIMIT 1), (SELECT id FROM app_management_machine OFFSET 1 LIMIT 1), (SELECT id FROM app_management_operator OFFSET 1 LIMIT 1), 'Very Urgent', 'Not yet', 'Another description of the bug', NOW(), NOW());