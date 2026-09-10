module.exports = {
  root: true,
  env: { browser: true, es2020: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  ignorePatterns: ["dist", ".eslintrc.cjs"],
  parser: "@typescript-eslint/parser",
  plugins: ["react-refresh"],
  rules: {
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
    // Hard rules per CLAUDE.md § 5 & .claude/agents/frontend-engineer.md:
    // Strict TypeScript; no any, no @ts-ignore
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/ban-ts-comment": [
      "error",
      {
        "ts-ignore": true,
        "ts-nocheck": true,
        "ts-check": false,
        "ts-expect-error": "allow-with-description",
      },
    ],
    "@typescript-eslint/no-unused-vars": [
      "error",
      { "argsIgnorePattern": "^_", "varsIgnorePattern": "^_" }
    ],
  },
};
