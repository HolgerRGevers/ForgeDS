# Mini playbook (test fixture)

## 2. Form Actions on expense_claims

### 2.1 On Add → On Validate

- **Script:**

```deluge
if(input.Email == null || input.Email == "")
{
    alert "Email is required.";
    cancel submit;
}
```

## 3. Custom Actions on expense_claims

### 3.1 LM_Approve — "LM Approve"

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending LM Approval"`
- **Success message:** `"LM approval recorded."`
- **Script:**

```deluge
input.Key_1_Approver = zoho.loginuser;
input.status = "Approved";
```
