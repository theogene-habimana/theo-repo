// Research projects listed on research-projects.html.
// To add a project: copy one object below, change its fields, and put its files in files/<folder>/.
// Each file entry is { "title": "...", "path": "file name inside files/<folder>/", "description": "..." }.
window.RESEARCH_PROJECTS = [
  {
    "id": "cybersecurity",
    "title": "Cybersecurity Risks and Corporate Financial Resilience",
    "icon": "fa-solid fa-shield-halved",
    "status": "Research in progress",
    "folder": "cybersecurity",
    "overview": "This project builds firm-level measures of cybersecurity risk by extracting and classifying cybersecurity-related disclosures from corporate annual reports filed with the U.S. SEC (EDGAR), and relates them to firms’ financing decisions, capital structure and financial resilience. It is part of research funded by the Foundation for Economic Education (LSR 2025, Application No. 32-16490).",
    "files": {
      "excel": [],
      "code": [
        {
          "title": "SEC EDGAR Cybersecurity Data Extraction",
          "path": "Sec_Edgar_Data_extraction.py",
          "description": "Download Python extraction script"
        }
      ],
      "results": [],
      "methodology": [
        {
          "title": "Cybersecurity Research Methodology",
          "path": "Methodology_Cyber.pdf",
          "description": "Download research methodology (PDF)"
        }
      ]
    }
  },
  {
    "id": "artificial-intelligence",
    "title": "Artificial Intelligence and Corporate Financing",
    "icon": "fa-solid fa-brain",
    "status": "Research in progress",
    "folder": "artificial-intelligence",
    "overview": "This project builds firm-level measures of artificial intelligence (AI) adoption by systematically extracting and analyzing AI-related disclosures in corporate annual reports, and examines how AI influences firms’ financing decisions and capital structures in developed and emerging markets. It is part of research funded by the Foundation for Economic Education (LSR 2025, Application No. 32-16490).",
    "files": {
      "excel": [],
      "code": [
        {
          "title": "Artificial Intelligence Data Extraction",
          "path": "ai_data_extraction_code.py",
          "description": "Download Python source code for extracting AI-related information from corporate annual reports"
        }
      ],
      "results": [],
      "methodology": [
        {
          "title": "Artificial Intelligence Research Methodology",
          "path": "Methodology_AI.pdf",
          "description": "Download the methodology for constructing firm-level AI measures"
        }
      ]
    }
  },
  {
    "id": "crowding-in",
    "title": "Crowding-in",
    "icon": "fa-solid fa-database",
    "status": "Published paper; data collection ongoing",
    "folder": "crowding-in",
    "overview": "This project develops a financial dataset covering 2,803 African companies—1,202 public and 1,601 private—across 29 countries. Initially covering 2000–2019, the dataset contains 22,737 firm-year observations and supported my doctoral dissertation at Hanken School of Economics. One of its three papers, coauthored with Gonul Colak and Timo Korkeamäki, was published in the Journal of International Business Studies (2025, 56:874–900). Data collection combines Python-based web scraping of annual reports and financial statements with manual verification. Accounting figures are extracted using extensive keyword matching, checked against source documents, and standardized for empirical analysis. The paper finds that external government borrowing crowds in corporate debt, particularly among publicly listed, larger, and internationally cross-listed firms, while domestic government borrowing crowds out corporate financing. The crowding-in relationship is stronger in countries active in Eurobond markets and following sovereign credit downgrades. Ongoing collection extends the dataset through 2026.",
    "files": {
      "excel": [],
      "code": [],
      "results": [],
      "methodology": [
        {
          "title": "Crowding-in Research Methodology",
          "path": "Methodology_Crowding_in.pdf",
          "description": "Download the data collection and measurement methodology (PDF)"
        }
      ]
    }
  }
];
