# Lifelog setup

Add these 5 secrets in GitHub: Settings -> Secrets and variables -> Actions -> New repository secret

| Name | Where to get it |
|-|-|
| TELEGRAM_TOKEN | @BotFather -> /newbot |
| TELEGRAM_CHAT_ID | message your bot, then open https://api.telegram.org/bot<TOKEN>/getUpdates and copy "chat":{"id": ...} |
| IG_TOKEN | Meta developer app -> Instagram -> API setup with Instagram login -> Generate access tokens |
| CLOUDINARY_URL | Cloudinary dashboard -> API environment variable (starts with cloudinary://) |
| GH_PAT | GitHub fine-grained token for this repo with "Secrets: Read and write" |

Test: send tagged items to your bot, then Actions -> post -> Run workflow.
Change post time: edit the cron line in .github/workflows/post.yml (UTC = IST minus 5:30).
