# Monzo Command Centre

A lightweight, high-performance, client-side financial engine and forecasting dashboard designed to parse Monzo CSV exports, track credit headroom, and project end-of-month balances.

---

## Features

* **Live Balance Tracking:** Input and locally persist your main account and Monzo Flex balances with automatic overdraft and credit limit monitoring.
* **Smart CSV Parser:** Automatically maps Monzo statement columns and features an intelligent categorization fallback engine to classify unlabelled transactions (e.g., groceries, transport, dining).
* **End-of-Month Forecasting:**
* **Scenario A:** Projects your pre-payday balance based on your current daily variable spend rate.
* **Scenario B:** Projects your pre-payday balance assuming a strict £20/day spending cap.


* **Visual Analytics:** Interactive Chart.js doughnut breakdown of variable spending and top merchant tracking.
* **100% Client-Side Privacy:** Built as a single-file web application—your financial data never leaves your browser and relies entirely on local storage.

---

## Tech Stack

* **HTML5 / Vanilla JavaScript (ES6+)**
* **Tailwind CSS** (via CDN)
* **PapaParse** (for fast client-side CSV parsing)
* **Chart.js** (for data visualization)

---
