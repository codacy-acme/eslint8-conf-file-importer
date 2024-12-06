module.exports = {
    env: {
        browser: true,
        es2021: true,
        node: true
    },
    plugins: ['vue', 'html', 'prettier', 'jsdoc', 'vuejs-accessibility'],
    extends: [
        'eslint:recommended',
        'plugin:vue/vue3-recommended',
        'plugin:storybook/recommended',
        'prettier',
        'plugin:jsdoc/recommended',
        'plugin:vuejs-accessibility/recommended'
    ],
    globals: {
        route: 'readonly',
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly'
    },
    overrides: [
        {
            files: [
                '**.js',
                '**/*.vue',
                '**/*.js',
                '**/*.jsx',
                '**/*.cjs',
                '**/*.mjs',
                '**/*.ts',
                '**/*.tsx'
            ]
        }
    ],
    parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module'
    },
    rules: {
        eqeqeq: ['error', 'always'],
        'vue/eqeqeq': ['error', 'always'],
        'vue/multi-word-component-names': 0,
        'vue/no-v-html': 0,
        'no-console': [
            'warn',
            {
                allow: ['warn', 'error']
            }
        ],
        'tailwindcss/no-custom-classname': 0,
        'tailwindcss/enforces-negative-arbitrary-values': 0,
        'storybook/no-redundant-story-name': 'off',
        'prefer-arrow-callback': 'error',
        'prettier/prettier':
            process.env.NODE_ENV === 'production' ? 'error' : 'warn',
        'no-unused-vars':
            process.env.NODE_ENV === 'production' ? 'error' : 'warn',
        'vue/no-unused-vars':
            process.env.NODE_ENV === 'production' ? 'error' : 'warn',
        'vue/attributes-order': [
            'warn',
            {
                order: [
                    'DEFINITION',
                    'LIST_RENDERING',
                    'CONDITIONALS',
                    'RENDER_MODIFIERS',
                    'GLOBAL',
                    ['UNIQUE', 'SLOT'],
                    'TWO_WAY_BINDING',
                    'OTHER_DIRECTIVES',
                    ['ATTR_STATIC', 'ATTR_SHORTHAND_BOOL'],
                    'ATTR_DYNAMIC',
                    'EVENTS',
                    'CONTENT'
                ],
                alphabetical: true
            }
        ],
        'vue/html-self-closing': [
            'warn',
            {
                html: { void: 'always', normal: 'always', component: 'always' },
                svg: 'always',
                math: 'always'
            }
        ],
        'jsdoc/require-param-description': 0,
        'jsdoc/require-returns-description': 0,
        'vuejs-accessibility/label-has-for': [
            'error',
            {
                components: ['AtomLabel'],
                controlComponents: ['MoleculeInput'],
                required: {
                    some: ['nesting', 'id']
                },
                allowChildren: true
            }
        ]
    }
}
