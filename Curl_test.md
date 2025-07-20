
# CivitAI Daemon Batch Test

## Model Test Data

| URN | Base Model | Filename | SHA256 |
|---|---|---|---|
| `urn:air:sdxl:lora:civitai:1791278@2027107` | Illustrious | sister_claire_ilxl_v1.safetensors | 2D3A79B94A62EC599BDCEC57358F968A2EE1CD6E9B3075AE6499007E58EE015C |
| `urn:air:sdxl:checkpoint:civitai:827184@1761560` | Illustrious | waiNSFWIllustrious_v140.safetensors | BDB59BAC77D94AE7A55FF893170F9554C3F349E48A1B73C0C17C0B7C6F4D41A2 |
| `urn:air:sdxl:vae:civitai:1684460@1906483` | Illustrious | illustriousXLV20_v10.safetensors | D7ED5CA5FD33FF846CF65F2EFBB36D7A259258CBB70DA71E711B2C612694AC00 |

---

## Get Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","role":"admin"}' | jq -r .access_token)
```

## Batch Download Request

```bash
curl -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "manifest": [
      {
          "model_id": "1791278",
          "model_version_id": "2027107",
          "model_type": "lora",
          "baseModel": "Illustrious",
          "sha256": "2D3A79B94A62EC599BDCEC57358F968A2EE1CD6E9B3075AE6499007E58EE015C",
          "url": "https://civitai.com/api/download/models/2027107",
          "filename": "sister_claire_ilxl_v1.safetensors"
      },
      {
          "model_id": "827184",
          "model_version_id": "1761560",
          "model_type": "checkpoint",
          "baseModel": "Illustrious",
          "sha256": "BDB59BAC77D94AE7A55FF893170F9554C3F349E48A1B73C0C17C0B7C6F4D41A2",
          "url": "https://civitai.com/api/download/models/1761560",
          "filename": "waiNSFWIllustrious_v140.safetensors",
          "priority": 1
      },
      {
          "model_id": "1684460",
          "model_version_id": "1906483",
          "model_type": "vae",
          "baseModel": "Illustrious",
          "sha256": "D7ED5CA5FD33FF846CF65F2EFBB36D7A259258CBB70DA71E711B2C612694AC00",
          "url": "https://civitai.com/api/download/models/1906483",
          "filename": "killustriousXLV20_v10.safetensors"
      }
    ]
  }'
```
