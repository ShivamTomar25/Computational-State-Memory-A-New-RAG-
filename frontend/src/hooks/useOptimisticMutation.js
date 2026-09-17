import { useMutation } from "@tanstack/react-query";

export function useOptimisticMutation(options) {
  return useMutation(options);
}
