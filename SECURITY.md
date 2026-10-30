# Security policy

## Supported versions

Only the latest release gets security fixes.

## Report a vulnerability

Do not open a public issue for a security problem. Use [GitHub private vulnerability reporting](https://github.com/devlnull/magenta-agents/security/advisories/new). Give the version, the steps to reproduce, and the impact. You get an answer in seven days.

## Security model

Know these limits before you use Magenta:

- **The guard and the hooks are guardrails, not a sandbox.** They stop mistakes of the agents: writes outside their files, access to secret paths, unsafe shell commands. They do not stop an attacker who controls the model. Some allowed commands (for example build tools) can run any code.
- **Checks run on your computer.** A check is a shell command. Approve only commands that you read and trust.
- **Untrusted input.** The agents treat PRDs, tickets, logs, and web pages as data, not as instructions. A prompt injection can still change the behavior of a model. Review the result before you merge.
- **Secrets.** The agents do not read `.env` files, keys, or `secrets/`. Keep secrets out of the repository anyway.
- **No push, merge, or deploy.** No agent has these permissions. A human does them.
