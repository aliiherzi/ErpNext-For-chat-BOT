# Try the bot from GitHub (Codespaces)

GitHub itself only stores the code. **GitHub Codespaces** gives you a temporary computer in the
browser that can run it: a throw-away ERPNext with the bot, a test company and test users.
Nothing here touches your real ERPNext.

## Start it

1. Open the repository on github.com and choose the branch that has this file
   (the branch button at the top left of the file list).
2. Green **Code** button > **Codespaces** tab > **Create codespace on ...**.
3. Wait. The first start downloads about 5 GB and builds the site: **15 to 20 minutes**.
   The terminal at the bottom shows the progress and ends with `==> Ready`.
   If no terminal shows, open one (menu > Terminal > New Terminal) and run `bash dev/start-demo.sh`.
4. Open the **PORTS** tab at the bottom, find port **8080**, and click the globe icon.

## Log in

| User | Password | What you see |
|---|---|---|
| `manager@example.com` | `Bot-test-12345` | The chat button at the bottom right |
| `Administrator` | `admin` | No chat button (by design); use it for Chatbot Settings |

The test company is "Test Books" (USD), with customers Ahmed Ali, Amina Hassan and
Walk-in Customer, and items Book ($5) and Pen ($1).

## Sentences to try first

Until you connect a real AI, a **scripted stand-in** answers. It only understands sentences
shaped like these (it is there to show the chat, the Confirm step and the documents):

- `I sold 2 book to Ahmed for 5 dollars each`
- `I sold 1 book for 3 dollars cash`
- `Waxaan Axmed ka iibiyay 2 buug`
- `Ahmed paid me 4`
- `what is the balance of Ahmed`
- `balance of everyone`
- `show me profit`
- `send me the pdf of ACC-SINV-2026-00001`

After a sale, press **Confirm / Haa**, then use the **Open** and **PDF** buttons.

## Connect a real AI

1. Create a key on openrouter.ai (free models need no payment).
2. Log in as Administrator, search for **Chatbot Settings**, and set:
   Provider `OpenAI-compatible`, Base URL `https://openrouter.ai/api/v1`,
   Model `google/gemma-4-26b-a4b-it:free`, and paste the key in **API key**. Save.
3. Log in as the manager again and write anything, in English or Somali.

For Claude instead: Provider `Claude`, Model `claude-haiku-5-5`, and the Anthropic key.

## Stop it

Codespaces uses your free monthly hours while it runs. When you finish:
github.com > **Code** > **Codespaces** > the `...` next to it > **Stop codespace**
(or **Delete** to free the storage too). Starting it again brings the demo back up.

## On your own PC instead

With Docker Desktop running, from the root of this repository:

```bash
bash dev/start-demo.sh
```

Then open http://localhost:8080. Port 8080 must be free, so stop your own ERPNext stack first.
