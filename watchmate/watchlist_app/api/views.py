from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status, throttling, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from watchlist_app.api import serializers
from watchlist_app.api.pagination import WatchListCPagination
from watchlist_app.api.permissions import IsAdminOrReadOnly, IsReviewUserOrReadOnly
from watchlist_app.api.throttling import ReviewCreateThrottle, ReviewListThrottle
from watchlist_app.models import Review, StreamPlatform, WatchList


class UserReview(generics.ListAPIView):
    serializer_class = serializers.ReviewSerializer

    def get_queryset(self):
        username = self.request.query_params.get("username", None)
        return Review.objects.filter(review_user__username=username)


class ReviewCreate(generics.CreateAPIView):
    serializer_class = serializers.ReviewSerializer
    permission_classes = [IsReviewUserOrReadOnly]
    throttle_classes = [ReviewCreateThrottle]

    def get_queryset(self):
        return Review.objects.all()

    def perform_create(self, serializer):
        pk = self.kwargs.get("pk")
        watchlist = WatchList.objects.get(pk=pk)

        review_user = self.request.user
        review_queryset = Review.objects.filter(
            watchlist=watchlist, review_user=review_user
        )

        if review_queryset.exists():
            raise ValidationError("You have already reviewed this watch")

        if watchlist.number_rating == 0:
            watchlist.avg_rating = serializer.validated_data["rating"]
        else:
            watchlist.avg_rating = (
                watchlist.avg_rating + serializer.validated_data["rating"]
            ) / 2

        watchlist.number_rating += 1
        watchlist.save()
        serializer.save(watchlist=watchlist, review_user=review_user)


class ReviewList(generics.ListAPIView):
    serializer_class = serializers.ReviewSerializer
    throttle_classes = [ReviewListThrottle]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["review_user__username", "active"]

    def get_queryset(self):
        pk = self.kwargs["pk"]
        return Review.objects.filter(watchlist=pk)


class ReviewDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Review.objects.all()
    serializer_class = serializers.ReviewSerializer
    permission_classes = [IsReviewUserOrReadOnly]
    throttle_classes = [throttling.UserRateThrottle, throttling.AnonRateThrottle]


class StreamPlatformVS(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = StreamPlatform.objects.all()
    serializer_class = serializers.StreamPlatformSerializer


class WatchListGV(generics.ListAPIView):
    queryset = WatchList.objects.all()
    serializer_class = serializers.WatchListSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["title"]
    pagination_class = WatchListCPagination


class WatchListAV(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [throttling.ScopedRateThrottle]
    throttle_scope = "watch-list"

    def get(self, request):
        watchlists = WatchList.objects.all()
        serializer = serializers.WatchListSerializer(watchlists, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = serializers.WatchListSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WatchDetailAV(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            watchlist = WatchList.objects.get(pk=pk)
        except WatchList.DoesNotExist:
            return Response({"message": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = serializers.WatchListSerializer(watchlist)
        return Response(serializer.data)

    def put(self, request, pk):
        watchlist = WatchList.objects.get(pk=pk)
        serializer = serializers.WatchListSerializer(watchlist, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        watchlist = WatchList.objects.get(pk=pk)
        watchlist.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
