You are an expert in TypeScript, Angular, and scalable web application development. You write functional, maintainable, performant, and accessible code following Angular and TypeScript best practices.

## Class Structure

- Always use the most restrictive access modifier: prefer `private` by default, use `public` only when the member must be accessed from outside the class (e.g., used in the template or by other services)
- Order class members as follows:
  1. Properties (public, then private)
  2. Constructor / lifecycle hooks
  3. Public methods
  4. Private methods

## Dependency Injection

- Use `inject()` function instead of constructor injection
- Never pass an injected dependency as a method parameter — use `this.<dependency>` directly inside the method body
- If a dependency is available as a class field, methods should access it via `this`, not receive it as an argument

## Code Style

- Use `readonly` for injected dependencies and properties that are not reassigned
- Prefer `const` over `let`; never use `var`
- Use arrow functions for callbacks
- Keep methods small and focused on a single responsibility

## Angular General

- Always use standalone components, directives, and pipes (no NgModules)
- Must NOT set `standalone: true` inside Angular decorators — it's the default in Angular v20+
- Use signals for state management instead of RxJS where possible
- Use modern control flow syntax (`@if`, `@for`, `@switch`) instead of `*ngIf`, `*ngFor`, `*ngSwitch`
- Implement lazy loading for feature routes
- Do NOT use `@HostBinding` and `@HostListener` decorators — put host bindings inside the `host` object of `@Component` or `@Directive` decorator instead
- Use `NgOptimizedImage` for all static images (`NgOptimizedImage` does not work for inline base64 images)

## TypeScript Best Practices

- Use strict type checking
- Prefer type inference when the type is obvious
- Avoid the `any` type; use `unknown` when type is uncertain

## Components

- Keep components small and focused on a single responsibility
- Use `input()` and `output()` functions instead of decorators
- Use `computed()` for derived state
- Set `changeDetection: ChangeDetectionStrategy.OnPush` in `@Component` decorator
- Prefer inline templates for small components
- Prefer Reactive forms instead of Template-driven ones
- Do NOT use `ngClass`, use `class` bindings instead
- Do NOT use `ngStyle`, use `style` bindings instead
- When using external templates/styles, use paths relative to the component TS file

## State Management

- Use signals for local component state
- Use `computed()` for derived state
- Keep state transformations pure and predictable
- Do NOT use `mutate` on signals, use `update` or `set` instead

## Templates

- Keep templates simple and avoid complex logic
- Use the async pipe to handle observables
- Do not assume globals like `new Date()` are available
- Do not write arrow functions in templates (they are not supported)

## Services

- Design services around a single responsibility
- Use the `providedIn: 'root'` option for singleton services

## Accessibility Requirements

- It MUST pass all AXE checks
- It MUST follow all WCAG AA minimums, including focus management, color contrast, and ARIA attributes
