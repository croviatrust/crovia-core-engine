# Contributing to CROVIA

Thank you for your interest in contributing to CROVIA.  
This project is designed as an **open-core, evidence-grade engine** for AI data
attribution, trust metrics, payouts, and governance.

Contributions must follow three principles that define the CROVIA philosophy:

1. **Verifiability** – Every change should be explainable, reproducible, and
   anchored in evidence.
2. **Clarity** – Code and documentation must be readable and auditable.
3. **Minimal surface area** – The engine should stay lean, modular, and focused.

---

## 1. Types of Contributions

You can contribute through:

- Fixes or improvements to the open-core engine  
- Enhancements to trust, payouts, floors, or hash-chain logic  
- Documentation improvements (docs/, README files, diagrams)  
- Example datasets or scripts  
- Bug reports and reproducible test cases  
- Security reports (see `SECURITY.md`)

---

## 2. Workflow

### 2.1. Fork → Branch → PR
1. Fork the repository  
2. Create a new branch:  
   `git checkout -b feature/<short-description>`
3. Commit logically grouped changes  
4. Submit a Pull Request (PR) using the CROVIA PR template  
5. A maintainer will review and provide feedback

---

## 3. Coding Standards

To maintain a consistent and audit-friendly codebase:

- Use **Python 3.10+**  
- Follow PEP8 where possible  
- Prefer pure-Python, dependency-minimal implementations  
- Avoid unnecessary abstractions or heavy frameworks  
- Ensure every new file includes a brief header explaining purpose and inputs/outputs  
- Include docstrings for all public functions  
- Add comments for non-obvious logic, especially around trust/payout computations  

---

## 4. Tests and Reproducibility

If your contribution affects core logic, include:

- minimal test cases  
- reproducible examples  
- expected vs. observed outputs  
- explanation of any change in trust, payout, or floor computations  

---

## 5. Documentation

Every new feature or script MUST be documented under `docs/`.  
Documentation is as important as code for auditability.

---

## 6. Respect and Conduct

All contributors must follow the **CROVIA Code of Conduct**.  
We value technical excellence, clarity, and respectful communication.

---

Thank you for helping strengthen CROVIA.
