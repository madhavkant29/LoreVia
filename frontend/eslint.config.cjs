const { FlatCompat } = require("@eslint/eslintrc")

const compat = new FlatCompat({
  baseDirectory: __dirname,
})

const eslintConfig = [
  ...compat.extends("next/core-web-vitals"),
  ...compat.extends("next/typescript"),
  {
    ignores: [".next/**", ".next-e2e*/**", "out/**", "dist/**", "coverage/**", "playwright-report/**", "test-results/**"],
  },
  {
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
  {
    rules: {
      // Remaining relaxations are tracked in the production-readiness backlog.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-require-imports": "off",
      "react/no-unescaped-entities": "off",
      "@next/next/no-img-element": "off",
      "@next/next/no-html-link-for-pages": "off",
      "@typescript-eslint/prefer-as-const": "error",
      "react-hooks/exhaustive-deps": "error",
      "@typescript-eslint/triple-slash-reference": "off",
      "@typescript-eslint/ban-ts-comment": "error",
      "no-unused-vars": "off",
      "no-console": ["error", { allow: ["warn", "error"] }],
      "prefer-const": "error",
      "no-var": "error",
      "@typescript-eslint/no-empty-object-type": "error",
      "react/jsx-no-useless-fragment": "off",
      "react/jsx-boolean-value": "off",
      "react/jsx-curly-brace-presence": "off",
      "@typescript-eslint/no-wrapper-object-types": "error",
      "@typescript-eslint/no-unsafe-function-type": "error",
    },
  },
  {
    files: ["scripts/**/*.{js,mjs,cjs}"],
    rules: {
      "no-console": "off",
    },
  },
]

module.exports = eslintConfig
