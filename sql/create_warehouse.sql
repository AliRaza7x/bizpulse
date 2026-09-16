CREATE DATABASE IF NOT EXISTS bizpulse
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE bizpulse;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id       VARCHAR(20) PRIMARY KEY,
    name              VARCHAR(150),
    email             VARCHAR(150),
    city              VARCHAR(100),
    country           VARCHAR(100),
    signup_date       DATE,
    customer_segment  VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id     VARCHAR(20) PRIMARY KEY,
    product_name   VARCHAR(200),
    category       VARCHAR(100),
    unit_cost      DECIMAL(12,2),
    unit_price     DECIMAL(12,2)
);

CREATE TABLE IF NOT EXISTS dim_campaign (
    campaign_id     VARCHAR(20) PRIMARY KEY,
    campaign_name   VARCHAR(200),
    platform        VARCHAR(50),
    start_date      DATE,
    end_date        DATE,
    budget          DECIMAL(12,2),
    objective       VARCHAR(50),
    target_segment  VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key       INT PRIMARY KEY,     -- YYYYMMDD
    full_date      DATE UNIQUE,
    day_of_week    VARCHAR(10),
    month_num      INT,
    month_name     VARCHAR(10),
    quarter_num    INT,
    year_num       INT,
    is_weekend     BOOLEAN
);

CREATE TABLE IF NOT EXISTS fact_sales (
    order_id        VARCHAR(20) PRIMARY KEY,
    order_date      DATETIME,
    date_key        INT,
    customer_id     VARCHAR(20),
    product_id      VARCHAR(20),
    quantity        INT,
    unit_price      DECIMAL(12,2),
    discount        DECIMAL(12,2),
    revenue         DECIMAL(12,2),
    cogs            DECIMAL(12,2),
    gross_margin    DECIMAL(12,2),
    payment_method  VARCHAR(50),
    channel         VARCHAR(50),
    order_status    VARCHAR(30),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    INDEX idx_fs_date (date_key)
);

CREATE TABLE IF NOT EXISTS fact_inventory (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date       DATE,
    date_key            INT,
    product_id          VARCHAR(20),
    warehouse_location  VARCHAR(100),
    stock_in            INT,
    stock_out           INT,
    closing_stock       INT,
    reorder_level       INT,
    is_below_reorder    BOOLEAN,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    INDEX idx_fi_date (date_key)
);

CREATE TABLE IF NOT EXISTS fact_marketing_spend (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    spend_date        DATE,
    date_key          INT,
    campaign_id       VARCHAR(20),
    platform          VARCHAR(50),
    impressions       INT,
    clicks            INT,
    spend             DECIMAL(12,2),
    leads_generated   INT,
    conversions       INT,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (campaign_id) REFERENCES dim_campaign(campaign_id),
    INDEX idx_fm_date (date_key)
);

CREATE TABLE IF NOT EXISTS fact_support_tickets (
    ticket_id              VARCHAR(20) PRIMARY KEY,
    created_date           DATETIME,
    date_key               INT,
    customer_id            VARCHAR(20),
    related_order_id       VARCHAR(20) NULL,
    channel                VARCHAR(50),
    category               VARCHAR(100),
    priority               VARCHAR(20),
    status                 VARCHAR(20),
    resolution_time_hours  DECIMAL(8,2) NULL,
    satisfaction_rating    TINYINT NULL,
    is_sla_breached        BOOLEAN,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    INDEX idx_ft_date (date_key)
);

CREATE OR REPLACE VIEW vw_monthly_revenue AS
SELECT d.year_num, d.month_num, d.month_name,
       SUM(f.revenue) AS total_revenue,
       SUM(f.cogs) AS total_cogs,
       SUM(f.gross_margin) AS total_gross_margin,
       COUNT(*) AS total_orders
FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status = 'Delivered'
GROUP BY d.year_num, d.month_num, d.month_name;

CREATE OR REPLACE VIEW vw_product_performance AS
SELECT p.product_id, p.product_name, p.category,
       SUM(f.quantity) AS units_sold,
       SUM(f.revenue) AS total_revenue,
       SUM(f.gross_margin) AS total_gross_margin
FROM fact_sales f JOIN dim_product p ON f.product_id = p.product_id
WHERE f.order_status = 'Delivered'
GROUP BY p.product_id, p.product_name, p.category;

CREATE OR REPLACE VIEW vw_stock_health AS
SELECT p.product_id, p.product_name, i.warehouse_location,
       i.closing_stock, i.reorder_level, i.is_below_reorder, i.snapshot_date
FROM fact_inventory i JOIN dim_product p ON i.product_id = p.product_id;

CREATE OR REPLACE VIEW vw_campaign_roi AS
SELECT c.campaign_id, c.campaign_name, c.platform,
       SUM(m.spend) AS total_spend,
       SUM(m.conversions) AS total_conversions,
       ROUND(SUM(m.spend) / NULLIF(SUM(m.conversions), 0), 2) AS cost_per_conversion
FROM fact_marketing_spend m JOIN dim_campaign c ON m.campaign_id = c.campaign_id
GROUP BY c.campaign_id, c.campaign_name, c.platform;

CREATE OR REPLACE VIEW vw_support_sla AS
SELECT d.year_num, d.month_num,
       COUNT(*) AS total_tickets,
       SUM(CASE WHEN is_sla_breached THEN 1 ELSE 0 END) AS breached_tickets,
       ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
       ROUND(AVG(satisfaction_rating), 2) AS avg_csat
FROM fact_support_tickets f JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year_num, d.month_num;
