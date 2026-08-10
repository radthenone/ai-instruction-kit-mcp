# An unrecognised Decision is reported, not fatal

A Profile naming a Decision the Kit does not know — `queue: kafka`, or a typo like `postgress` — resolves successfully and is listed as unrecognised in the instruction index. It does not stop the MCP server from starting.

Fail-fast is the obvious alternative and we rejected it deliberately. The server starts inside the user's IDE, launched by a client configuration they may not have written; a hard startup failure surfaces to them as "the MCP server is broken" with no indication that a single line of YAML is at fault. Reporting through the index reuses the pattern the Kit already has for Instruction Modules a Bundle references but cannot find.

The failure mode this accepts is a Profile quietly getting fewer instructions than intended. That is the trade: a visible-but-degraded server over an invisible-and-dead one.
