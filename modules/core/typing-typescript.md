# TypeScript — standardy typowania (frontend)

## Zasady ogólne

- **`strict: true`** w `tsconfig.json` — bez wyjątków w nowym kodzie.
- **Zero `any`** — użyj `unknown` + type guard, generics lub typów z Orval.
- Eksportuj typy props komponentów: `type CheckoutScreenProps = { orderId: string }`.
- Preferuj `interface` dla obiektów publicznych API modułu, `type` dla unii i utility.

## Typy z API (Orval)

```text
frontend/src/api/generated/   ← NIE edytuj ręcznie
```

- Po zmianie schema: `task ovral:generate` → `task lints:frontend:typecheck`.
- Hooki TanStack Query typują `data` z generated types:

```typescript
import type { OrderDetail } from "@/api/generated/models";

export function useOrder(orderId: string) {
  return useQuery<OrderDetail>({
    queryKey: ["orders", orderId],
    queryFn: () => ordersApi.retrieve(orderId),
  });
}
```

## Query keys — typowane stałe

```typescript
// src/core/query/keys.ts
export const orderKeys = {
  all: ["orders"] as const,
  detail: (id: string) => [...orderKeys.all, id] as const,
};
```

Unika magic strings i ułatwia invalidację.

## Zustand — tylko client state

```typescript
type CartState = {
  items: CartLine[];
  addItem: (line: CartLine) => void;
  clear: () => void;
};

export const useCartStore = create<CartState>((set) => ({
  // ...
}));
```

**Nie** trzymaj `OrderDetail[]` z API w Zustand — to TanStack Query.

## Formularze — Zod + RHF

```typescript
const addressSchema = z.object({
  street: z.string().min(1),
  city: z.string().min(1),
  postalCode: z.string().regex(/^\d{2}-\d{3}$/),
});

type AddressFormValues = z.infer<typeof addressSchema>;
```

Jeden schema = walidacja + typ — DRY.

## Platform files

- Wspólne typy w `types.ts` obok `.native.tsx` / `.web.tsx`.
- Nie duplikuj interfejsów między platformami.

## Powiązane

- `stack:expo-router:mobile-native`
- `arch:api-contract`
