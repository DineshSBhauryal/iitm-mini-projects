INSERT OR IGNORE INTO evaluation_criteria (criterion_id, name, description, weight, max_score, is_active)
VALUES
    (1, 'Technical Capability', 'Architecture, integrations, scalability, technical fit', 30, 10, 1),
    (2, 'Implementation Plan', 'Timeline, milestones, staffing, risk plan', 20, 10, 1),
    (3, 'Commercial Value', 'Pricing clarity, total cost, assumptions', 20, 10, 1),
    (4, 'Security & Compliance', 'Controls, certifications, privacy, auditability', 20, 10, 1),
    (5, 'Support & Experience', 'Support model, similar projects, references', 10, 10, 1);
