import { InfiniteData, QueryKey, useMutation, useQueryClient } from "@tanstack/react-query";
import { feedApi, FeedPost, PaginatedPosts } from "../api/feed";
import { placesApi } from "../api/places";

type Feed = InfiniteData<PaginatedPosts>;

/** Optimistic like/save toggles for any infinite list of posts. */
export function usePostActions(queryKey: QueryKey) {
  const qc = useQueryClient();

  const patch = (fn: (p: FeedPost) => FeedPost) =>
    qc.setQueryData<Feed>(queryKey, (old: Feed | undefined) =>
      old && { ...old, pages: old.pages.map((page: PaginatedPosts) => ({ ...page, items: page.items.map(fn) })) }
    );

  const optimistic = <V>(apply: (v: V) => (p: FeedPost) => FeedPost) => ({
    onMutate: async (v: V) => {
      await qc.cancelQueries({ queryKey });
      const prev = qc.getQueryData<Feed>(queryKey);
      patch(apply(v));
      return { prev };
    },
    onError: (_e: unknown, _v: V, ctx?: { prev?: Feed }) => qc.setQueryData(queryKey, ctx?.prev),
  });

  const like = useMutation({
    mutationFn: (post: FeedPost) => (post.is_liked_by_me ? feedApi.unlikePost(post.id) : feedApi.likePost(post.id)),
    ...optimistic<FeedPost>((post) => (p) =>
      p.id === post.id
        ? { ...p, is_liked_by_me: !post.is_liked_by_me, like_count: p.like_count + (post.is_liked_by_me ? -1 : 1) }
        : p
    ),
  });

  const save = useMutation({
    mutationFn: (post: FeedPost) => (post.is_saved_by_me ? placesApi.unsave(post.place.id) : placesApi.save(post.place.id)),
    // Saving is per place, so every post at that place flips together.
    ...optimistic<FeedPost>((post) => (p) =>
      p.place.id === post.place.id ? { ...p, is_saved_by_me: !post.is_saved_by_me } : p
    ),
    onSettled: () => qc.invalidateQueries({ queryKey: ["saved-places"] }),
  });

  return { like: like.mutate, save: save.mutate };
}
